import openai
import pymongo
from flask import Flask, request, jsonify
from wiki_source import ENCODING, WikiSource, num_tokens_from_string
from flask_cors import CORS
import time
import os

app = Flask(__name__)
CORS(app)
openai_client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
MONGO_URI = os.getenv("MONGO_URI")

BATCH_SIZE = 1000
FLAG_THRESHOLD = -0.5
EMBEDDING_MODEL = "text-embedding-3-small"

mongo_client = pymongo.MongoClient(MONGO_URI)
db = mongo_client["smart_notes"]
notes_collection = db["notes"]
sources_collection = db["sources"]
notebook_collection = db["notebooks"]

"""
Example MongoDB Collection Structure:
notebook_document = {
    "_id": ObjectId(),
    "name": "Research Notes",
    "note_ids": [ObjectId("note1_id"), ObjectId("note2_id")],
    "source_id": ObjectId("source1_id")
}

note_document = {
    "_id": ObjectId(),
    "content": "This is a note about...",
    "notebook_id": ObjectId("notebook1_id"),
    "embedding": [0.1, 0.2, 0.3],
    "contradicting_info": [
        {
            "text": "This is contradicting information",
            "score": 0.5
        }
    ]
}

source_document = {
    "_id": ObjectId(),
    "name": "Research Paper Title",
    "strings": [
        "This is a string about...",
        "This is another string about..."
    ],
    "embeddings": [
        [0.1, 0.2, 0.3],
        [0.4, 0.5, 0.6]
    ],
    "link": "some wikipedia link"
}
"""

def generate_embedding(text):
    return openai.embeddings.create(input=[text], model="text-embedding-3-small").data[0].embedding

def embed_wiki_source(category_page: str):
    parser = WikiSource(category_page)
    titles = parser.titles_from_category(parser.get_category_page(), max_depth=1)
    print(f"Found {len(titles)} article titles in {category_page}.")

    wikipedia_sections = []
    for title in titles:
        wikipedia_sections.extend(parser.all_subsections_from_title(title))
    print(f"Found {len(wikipedia_sections)} sections in {len(titles)} pages.")

    wikipedia_sections = [parser.clean_section(ws) for ws in wikipedia_sections]
    original_num_sections = len(wikipedia_sections)
    wikipedia_sections = [ws for ws in wikipedia_sections if parser.keep_section(ws)]
    print(f"Filtered out {original_num_sections-len(wikipedia_sections)} sections, leaving {len(wikipedia_sections)} sections.")

    wikipedia_strings = []
    for section in wikipedia_sections:
        wikipedia_strings.extend(parser.split_strings_from_subsection(section, max_tokens=1600))
    
    tokens_per_string = [num_tokens_from_string(string, ENCODING) for string in wikipedia_strings]

    print(f"{len(wikipedia_sections)} Wikipedia sections split into {len(wikipedia_strings)} strings.")
    print(f"Total tokens: {parser.total_tokens}")

    embeddings = []
    for batch_start in range(0, len(wikipedia_strings), BATCH_SIZE):
        batch_end = batch_start + BATCH_SIZE
        batch = wikipedia_strings[batch_start:batch_end]
        print(f"Batch {batch_start} to {batch_end-1}")
        response = openai_client.embeddings.create(model=EMBEDDING_MODEL, input=batch)
        for i, be in enumerate(response.data):
            assert i == be.index  # double check embeddings are in same order as input
        batch_embeddings = [e.embedding for e in response.data]
        embeddings.extend(batch_embeddings)

    return (wikipedia_strings, embeddings)

def flag_incorrect_info(query: str):
    # Generate embedding for query
    query_embedding = generate_embedding(query)
    
    sources_collection.create_search_index(
    {"definition":
        {"mappings": {"dynamic": True, "fields": {
            "embeddings" : {
                "dimensions": 1536,
                "similarity": "dotProduct",
                "type": "knnVector"
                }}}},
     "name": "source_embeddings_index",
    })

    results = sources_collection.aggregate([
    {
        '$vectorSearch': {
            "index": "source_embeddings_index",
            "path": "embeddings",
            "queryVector": query_embedding,
            "numCandidates": 50,
            "limit": 5,
        }
    },
    { "$sort": { "score": 1 } }
    ])

    flagged_sources = []
    for doc in results:
        if doc["score"] < FLAG_THRESHOLD:
            flagged_sources.append({
                "text": doc["text"],
                "score": doc["score"],
                "wikipedia_link": doc["link"]
            })
    
    return {"flagged_sources": flagged_sources}

@app.route("/create_notebook", methods=["POST"])
def create_notebook():
    data = request.json
    notebook_name = data["notebook_name"]
    category_page = data["category_page"]
    wiki_strings, embeddings = embed_wiki_source(category_page)
    notebook_collection.insert_one({"name": notebook_name, "notes": [], "source": {"strings": wiki_strings, "embeddings": embeddings}})
    return jsonify({"message": "Notebook created successfully!"})

@app.route("/add_note", methods=["POST"])
def add_note():
    data = request.json
    notebook_id = data["notebook_id"]
    note_text = data["note"]
    
    embedding = generate_embedding(note_text)
    
    contradicting_info = flag_incorrect_info(note_text)

    notes_collection.insert_one({
        "content": note_text,
        "embedding": embedding,
        "notebook_id": notebook_id,
        "contradicting_info": contradicting_info
    })

    note_id = notes_collection.find_one({"content": note_text})["_id"]
    notebook_collection.update_one(
        {"_id": notebook_id},
        {"$push": {"notes": note_id}}
    )
    
    return jsonify({"message": "Note saved successfully!"})

@app.route("/get_all_notebooks", methods=["GET"])
def get_all_notebooks():
    notebooks = notebook_collection.find()
    return jsonify([{"id": str(notebook["_id"]), "name": notebook["name"]} for notebook in notebooks])

@app.route("/get_notes_for_notebook", methods=["GET"])
def get_notes_for_notebook():
    notebook_id = request.args.get("notebook_id")
    return jsonify([{"id": str(note["_id"]), "content": note["content"]} for note in notes_collection.find({"notebook_id": notebook_id})])

@app.route("/get_note", methods=["GET"])
def get_note():
    note_id = request.args.get("note_id")
    return jsonify(notes_collection.find_one({"_id": note_id}))

@app.route("/update_note", methods=["PUT"])
def update_note():
    data = request.json
    note_id = data["note_id"]
    note_text = data["note"]
    
    embedding = generate_embedding(note_text)
    
    notes_collection.replace_one({"_id": note_id}, {"text": note_text, "embedding": embedding})
    
    return jsonify({"message": "Note saved successfully!"})

@app.route("/learn_more", methods=["GET"])
def learn_more():
    note_id = request.args.get("note_id")
    note = notes_collection.find_one({"_id": note_id})
    
    # Create index on source embeddings array
    sources_collection.create_search_index(
    {"definition":
        {"mappings": {"dynamic": True, "fields": {
            "embeddings" : {
                "dimensions": 1536,
                "similarity": "dotProduct",
                "type": "knnVector"
                }}}},
     "name": "source_embeddings_index",
    })

    results = sources_collection.aggregate([
    {
        '$vectorSearch': {
            "index": "source_embeddings_index",
            "path": "embeddings",
            "queryVector": note["embedding"],
            "numCandidates": 50,
            "limit": 5,
        }
    },
    {
        # Project to get the corresponding string and link for each matching embedding
        '$project': {
            'string': {
                '$arrayElemAt': [
                    '$strings',
                    {
                        '$indexOfArray': ['$embeddings', '$vectorSearchScore.embedding']
                    }
                ]
            },
            'link': 1,  # Include the Wikipedia link
            'name': 1,  # Include the source name
            'score': '$vectorSearchScore'
        }
    }
    ])
    
    # Format results for response
    formatted_results = []
    for result in results:
        formatted_results.append({
            "text": result["string"],
            "source_name": result["name"],
            "wikipedia_link": result["link"],
            "score": result["score"]
        })
    
    return jsonify({
        "results": formatted_results,
    })

app.run(debug=True)
