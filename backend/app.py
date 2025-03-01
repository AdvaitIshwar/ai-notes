import openai
import pymongo
from flask import Flask, request, jsonify
from wiki_source import ENCODING, WikiSource, num_tokens_from_string
from flask_cors import CORS
import os
from dotenv import load_dotenv
from pinecone import Pinecone, ServerlessSpec
import uuid
from bson import ObjectId

load_dotenv(dotenv_path=".env")

app = Flask(__name__)
CORS(app)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
MONGO_URI = os.getenv("MONGO_URI")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")

openai_client = openai.OpenAI(api_key=OPENAI_API_KEY)
mongo_client = pymongo.MongoClient(MONGO_URI)

# Initialize Pinecone
pc = Pinecone(api_key=PINECONE_API_KEY)
index = "smart-notes"

# Check if index exists, if not create it
if index not in pc.list_indexes().names():
    pc.create_index(
        name=index,
        dimension=1536,
        metric="cosine",
        spec=ServerlessSpec(
            cloud="aws",
            region="us-east-1"
        )
    )

# Connect to the index
index = pc.Index(index)

BATCH_SIZE = 1000
FLAG_THRESHOLD = -0.5
EMBEDDING_MODEL = "text-embedding-3-small"

db = mongo_client["smart_notes"]
notes_collection = db["notes"]
notebook_collection = db["notebooks"]

"""
MongoDB Schema:
notebook_document = {
    "_id": ObjectId(),
    "name": "Research Notes",
    "notes": [ObjectId("note1_id"), ObjectId("note2_id")],
    "category_page": "Category:Artificial_intelligence"
}

note_document = {
    "_id": ObjectId(),
    "content": "This is a note about...",
    "notebook_id": ObjectId("notebook1_id"),
    "vector_id": "unique_vector_id",  # Reference to Pinecone vector
    "contradicting_info": [
        {
            "text": "This is contradicting information",
            "score": 0.5,
            "wikipedia_link": "https://..."
        }
    ]
}

Pinecone Schema:
{
    "id": "unique_vector_id",
    "values": [embedding vector],
    "metadata": {
        "text": "Original text content",
        "type": "note/source",
        "wikipedia_link": "https://..." (for source vectors),
        "notebook_id": "notebook_id" (for organizing vectors by notebook)
    }
}
"""

def generate_embedding(text):
    return openai_client.embeddings.create(input=[text], model=EMBEDDING_MODEL).data[0].embedding

def embed_wiki_source(category_page: str, notebook_id: str):
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
    
    print(f"{len(wikipedia_sections)} Wikipedia sections split into {len(wikipedia_strings)} strings.")

    # Process in batches
    vectors_to_upsert = []
    for batch_start in range(0, len(wikipedia_strings), BATCH_SIZE):
        batch_end = batch_start + BATCH_SIZE
        batch = wikipedia_strings[batch_start:batch_end]
        print(f"Processing batch {batch_start} to {batch_end-1}")
        
        response = openai_client.embeddings.create(model=EMBEDDING_MODEL, input=batch)
        batch_embeddings = [e.embedding for e in response.data]
        
        # Prepare vectors for Pinecone
        for text, embedding in zip(batch, batch_embeddings):
            vector_id = str(uuid.uuid4())
            vectors_to_upsert.append({
                "id": vector_id,
                "values": embedding,
                "metadata": {
                    "text": text,
                    "type": "source",
                    "notebook_id": notebook_id,
                    "wikipedia_link": f"https://en.wikipedia.org/wiki/{category_page}"
                }
            })
    
    # Upsert to Pinecone in smaller batches
    PINECONE_BATCH_SIZE = 100
    for i in range(0, len(vectors_to_upsert), PINECONE_BATCH_SIZE):
        batch = vectors_to_upsert[i:i + PINECONE_BATCH_SIZE]
        index.upsert(vectors=batch)

def flag_incorrect_info(query: str, query_embedding, notebook_id: str):
    negative_query_embedding = [-x for x in query_embedding]
    
    results = index.query(
        vector=negative_query_embedding,
        filter={
            "type": "source",
            "notebook_id": notebook_id
        },
        top_k=5,
        include_metadata=True
    )
    
    flagged_sources = []
    for match in results.matches:
        actual_similarity = -match.score
        flagged_sources.append({
            "text": match.metadata["text"],
            "score": actual_similarity,
            "wikipedia_link": match.metadata["wikipedia_link"]
        })
    
    return flagged_sources

@app.route("/create_notebook", methods=["POST"])
def create_notebook():
    data = request.json
    notebook_name = data["notebook_name"]
    category_page = data["category_page"]
    
    result = notebook_collection.insert_one({
        "name": notebook_name,
        "notes": [],
        "category_page": category_page
    })
    notebook_id = str(result.inserted_id)
    
    embed_wiki_source(category_page, notebook_id)
    
    return jsonify({"message": "Notebook created successfully!", "notebook_id": notebook_id})

@app.route("/add_note", methods=["POST"])
def add_note():
    data = request.json
    notebook_id = data["notebook_id"]
    note_text = data["note"]
    
    embedding = generate_embedding(note_text)
    vector_id = str(uuid.uuid4())
    
    index.upsert(
        vectors=[{
            "id": vector_id,
            "values": embedding,
            "metadata": {
                "text": note_text,
                "type": "note",
                "notebook_id": notebook_id
            }
        }]
    )
    
    contradicting_info = flag_incorrect_info(note_text, embedding, notebook_id)
    
    note = {
        "content": note_text,
        "vector_id": vector_id,
        "notebook_id": notebook_id,
        "contradicting_info": contradicting_info
    }
    result = notes_collection.insert_one(note)
    
    notebook_collection.update_one(
        {"_id": ObjectId(notebook_id)},
        {"$push": {"notes": result.inserted_id}}
    )
    
    return jsonify({"message": "Note saved successfully!"})

@app.route("/get_all_notebooks", methods=["GET"])
def get_all_notebooks():
    notebooks = list(notebook_collection.find())
    response = []
    
    for notebook in notebooks:
        # Get all notes for this notebook
        notebook_notes = list(notes_collection.find({"notebook_id": str(notebook["_id"])}))
        response.append({
            "id": str(notebook["_id"]),
            "name": notebook["name"],
            "notes": [{
                "id": str(note["_id"]),
                "content": note["content"],
                "contradicting_info": note.get("contradicting_info", [])
            } for note in notebook_notes]
        })
    
    return jsonify(response)

@app.route("/get_note", methods=["GET"])
def get_note():
    note_id = request.args.get("note_id")
    note = notes_collection.find_one({"_id": ObjectId(note_id)})
    if note:
        return jsonify({
            "id": str(note["_id"]),
            "content": note["content"],
            "contradicting_info": note["contradicting_info"]
        })
    return jsonify({"error": "Note not found"}), 404

@app.route("/get_notes", methods=["GET"])
def get_notes():
    notebook_id = request.args.get("notebook_id")
    notes = notes_collection.find({"notebook_id": notebook_id})
    return jsonify([{
        "id": str(note["_id"]),
        "content": note["content"],
        "contradicting_info": note["contradicting_info"]
    } for note in notes])


@app.route("/learn_more", methods=["GET"])
def learn_more():
    note_id = request.args.get("note_id")
    note = notes_collection.find_one({"_id": ObjectId(note_id)})
    
    if not note:
        return jsonify({"error": "Note not found"}), 404
    
    vector = index.fetch([note["vector_id"]])
    if not vector.vectors:
        return jsonify({"error": "Vector not found"}), 404
    
    results = index.query(
        vector=vector.vectors[note["vector_id"]].values,
        filter={
            "type": "source",
            "notebook_id": note["notebook_id"]
        },
        top_k=5,
        include_metadata=True
    )
    
    formatted_results = []
    for match in results.matches:
        formatted_results.append({
            "string": match.metadata["text"],
            "name": "Wikipedia",
            "link": match.metadata["wikipedia_link"],
            "score": match.score
        })
    
    return jsonify({"results": formatted_results})


if __name__ == "__main__":
    app.run(debug=True)
