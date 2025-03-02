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
THRESHOLD = 0.75
EMBEDDING_MODEL = "text-embedding-3-small"
GPT_MODEL = "gpt-4o-mini"

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
    "related_info": [
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

def get_related_info(query_embedding: list[float]):
    results = index.query(
        vector=query_embedding,
        filter={"type": "source"},
        top_k=3,
        include_metadata=True
    )
    related_info = []
    for match in results.matches:
        related_info.append({
            "text": match.metadata["text"],
            "score": match.score,
            "wikipedia_link": match.metadata["wikipedia_link"]
        })
    
    return related_info

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

    related_info = get_related_info(embedding)
    
    note = {
        "content": note_text,
        "vector_id": vector_id,
        "notebook_id": notebook_id,
        "related_info": related_info
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
                "related_info": note.get("related_info", [])
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
            "related_info": note["related_info"]
        })
    return jsonify({"error": "Note not found"}), 404

@app.route("/get_notes", methods=["GET"])
def get_notes():
    notebook_id = request.args.get("notebook_id")
    notes = notes_collection.find({"notebook_id": notebook_id})
    return jsonify([{
        "id": str(note["_id"]),
        "content": note["content"],
        "related_info": note["related_info"]
    } for note in notes])

@app.route("/resolve_potential_misinformation", methods=["GET"])
def resolve_potential_misinformation():
    note_id = request.args.get("note_id")
    note = notes_collection.find_one({"_id": ObjectId(note_id)})
    
    if not note:
        return jsonify({"error": "Note not found"}), 404
    
    vector = index.fetch([note["vector_id"]])
    if not vector.vectors:
        return jsonify({"error": "Vector not found"}), 404
    
    top_related_info = note["related_info"]
    top_related_info_scores = [info["score"] for info in top_related_info]
    if max(top_related_info_scores) < THRESHOLD:
        top_related_info_string = "\n\n".join([f"Source {i+1}:\n{info['text']}" for i, info in enumerate(top_related_info)])
        print(top_related_info_string)
    else:
        return jsonify({"message": "No potential misinformation found"})
    
    prompt = f"""
    Given a statement, and a list of related information that are considered to be factual,
    determine if the statement is factually inaccurate.
    If it is, correct the statement to be factually accurate and print out the corrected statement in the following format: "Corrected statement: <statement>".
    Please also print which of the sources provided were used to correct the statement in the following format: 
    "Sources used: <source1>, <source2>, <source3>".
    If not print "Statement is factually accurate".
    The statement is: {note["content"]}
    The top 3 related information from Wikipedia are: {top_related_info_string}
    """
    
    response = openai_client.chat.completions.create(
        model=GPT_MODEL,
        messages=[{"role": "system", "content": "You are a helpful assistant that resolves potential misinformation in a note."}, 
                  {"role": "user", "content": prompt}]
    )

    if "Corrected statement:" in response.choices[0].message.content:
        corrected_statement = response.choices[0].message.content.replace("Corrected statement: ", "")
    
    return jsonify({"response": response.choices[0].message.content})

@app.route("/delete_note", methods=["DELETE"])
def delete_note():
    note_id = request.args.get("note_id")
    notes_collection.delete_one({"_id": ObjectId(note_id)})
    return jsonify({"message": "Note deleted successfully!"})
    


if __name__ == "__main__":
    app.run(debug=True)
