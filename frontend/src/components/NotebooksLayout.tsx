// src/components/NotebooksLayout.tsx
import React, { useState, useEffect } from "react";
import axios from "axios";

interface Note {
  _id: string;
  content: string;
  contradicting_info: Array<{
    text: string;
    score: number;
    wikipedia_link: string;
  }>;
}

interface Notebook {
  _id: string;
  name: string;
  notes: Note[];
}

export default function NotebooksLayout() {
  const [notebooks, setNotebooks] = useState<Notebook[]>([]);
  const [selectedNotebook, setSelectedNotebook] = useState<string | null>(null);
  const [selectedNote, setSelectedNote] = useState<Note | null>(null);
  const [isCreatingNotebook, setIsCreatingNotebook] = useState(false);
  const [newNotebookName, setNewNotebookName] = useState("");
  const [categoryPage, setCategoryPage] = useState("");
  const [relatedInfo, setRelatedInfo] = useState<
    Array<{
      string: string;
      name: string;
      link: string;
      score: number;
    }>
  >([]);
  const [isLoading, setIsLoading] = useState(false);
  useEffect(() => {
    fetchNotebooks();
  }, []);

  const fetchNotebooks = async () => {
    try {
      const response = await axios.get(
        "http://localhost:5000/get_all_notebooks"
      );
      setNotebooks(response.data);
      if (response.data.length > 0 && !selectedNotebook) {
        setSelectedNotebook(response.data[0]._id);
      }
    } catch (error) {
      console.error("Error fetching notebooks:", error);
    }
  };

  const addNote = async (notebookId: string, noteContent: string) => {
    try {
      await axios.post("http://localhost:5000/add_note", {
        notebook_id: notebookId,
        note: noteContent,
      });
      fetchNotebooks(); // Refresh the notebooks to get the new note
    } catch (error) {
      console.error("Error adding note:", error);
    }
  };

  const handleCreateNotebook = async () => {
    try {
      setIsLoading(true);
      await axios.post("http://127.0.0.1:5000/create_notebook", {
        notebook_name: newNotebookName,
        category_page: categoryPage,
      });
      setIsCreatingNotebook(false);
      setNewNotebookName("");
      setCategoryPage("");
      fetchNotebooks();
    } catch (error) {
      console.error("Error creating notebook:", error);
    } finally {
      setIsLoading(false);
    }
  };

  const getNote = async (noteId: string) => {
    const response = await axios.get(
      `http://localhost:5000/get_note?note_id=${noteId}`
    );
    setSelectedNote(response.data);
  };

  const learnMore = async (noteId: string) => {
    const response = await axios.get(
      `http://localhost:5000/learn_more?note_id=${noteId}`
    );
    setRelatedInfo(response.data.results);
  };

  return (
    <div className="flex flex-col h-screen bg-background">
      {/* Top Navigation - Notebooks */}
      <div className="bg-primary py-4 px-6 flex items-center justify-between">
        <div className="flex space-x-4 overflow-x-auto">
          {notebooks.map((notebook) => (
            <button
              key={notebook._id}
              onClick={() => {
                setSelectedNotebook(notebook._id);
                setSelectedNote(null);
              }}
              className={`text-primary-foreground font-semibold border-b-2 px-4 py-2 rounded-lg hover:bg-primary/20 focus:outline-none focus:bg-primary/20 ${
                selectedNotebook === notebook._id
                  ? "border-primary-foreground"
                  : "border-transparent"
              }`}
            >
              {notebook.name}
            </button>
          ))}
          <button
            onClick={() => setIsCreatingNotebook(true)}
            className="text-primary-foreground font-semibold border-b-2 border-transparent px-4 py-2 rounded-lg hover:bg-primary/20 focus:outline-none focus:bg-primary/20"
          >
            + New Notebook
          </button>
        </div>
      </div>

      <div className="flex flex-1">
        {/* Notes Sidebar */}
        <div className="bg-card w-1/4 p-4 overflow-y-auto">
          {selectedNotebook && (
            <>
              {/* <button
                onClick={() => addNote(selectedNotebook)}
                className="bg-secondary text-secondary-foreground px-4 py-2 rounded-lg w-full mb-4 hover:bg-secondary/80 focus:outline-none focus:bg-secondary/80"
              >
                + New Note
              </button> */}
              {notebooks
                .find((n) => n._id === selectedNotebook)
                ?.notes.map((note) => (
                  <button
                    key={note._id}
                    onClick={() => {
                      setSelectedNote(note);
                      getNote(note._id);
                    }}
                    className={`bg-secondary text-secondary-foreground px-4 py-2 rounded-lg w-full mb-2 hover:bg-secondary/80 focus:outline-none focus:bg-secondary/80 ${
                      selectedNote?._id === note._id
                        ? "ring-2 ring-primary"
                        : ""
                    }`}
                  >
                    <p className="truncate text-left">
                      {note.content.substring(0, 50)}...
                    </p>
                    {note.contradicting_info.length > 0 && (
                      <div className="flex items-center mt-2 text-yellow-500 text-sm">
                        <svg
                          className="h-4 w-4 mr-1"
                          fill="currentColor"
                          viewBox="0 0 20 20"
                        >
                          <path
                            fillRule="evenodd"
                            d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z"
                            clipRule="evenodd"
                          />
                        </svg>
                        Contradictions found
                      </div>
                    )}
                  </button>
                ))}
            </>
          )}
        </div>

        {/* Main Content Area */}
        <div className="bg-card w-3/4 p-4 overflow-y-auto">
          {selectedNote ? (
            <div className="space-y-6">
              <div className="prose max-w-none">
                <p className="text-lg">{selectedNote.content}</p>
              </div>

              {selectedNote.contradicting_info.length > 0 && (
                <div className="bg-yellow-50 rounded-lg p-6">
                  <h3 className="text-yellow-800 font-medium mb-4">
                    Contradicting Information
                  </h3>
                  <div className="space-y-4">
                    {selectedNote.contradicting_info.map((info, index) => (
                      <div key={index} className="flex items-start">
                        <div className="flex-1">
                          <p className="text-yellow-700">{info.text}</p>
                          <p className="text-yellow-600 text-sm mt-1">
                            Confidence Score: {info.score}
                          </p>
                        </div>
                        <a
                          href={info.wikipedia_link}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="ml-4 text-blue-600 hover:text-blue-800"
                        >
                          View Source
                        </a>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {relatedInfo ? (
                <div className="space-y-4">
                  <h3 className="text-lg font-medium">Related Information</h3>
                  {relatedInfo.map((info, index) => (
                    <div key={index} className="bg-gray-50 rounded-lg p-4">
                      <p className="text-gray-800">{info.string}</p>
                      <div className="mt-2 flex justify-between items-center">
                        <span className="text-sm text-gray-600">
                          {info.name}
                        </span>
                        <a
                          href={info.link}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-blue-600 hover:text-blue-800 text-sm"
                        >
                          View Source
                        </a>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <button
                  onClick={async () => {
                    await learnMore(selectedNote._id);
                  }}
                  className="bg-blue-600 text-white px-6 py-3 rounded-md hover:bg-blue-700"
                >
                  Learn More
                </button>
              )}
            </div>
          ) : (
            <div className="h-full flex items-center justify-center text-muted-foreground">
              <p>Select a notebook or create a new one</p>
            </div>
          )}
        </div>
      </div>

      {/* Create Notebook Modal */}
      {isCreatingNotebook && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50">
          <div className="bg-card rounded-lg shadow-xl max-w-md w-full p-6">
            <div className="flex justify-between items-center mb-6">
              <h2 className="text-xl font-semibold">Create New Notebook</h2>
              <button
                onClick={() => setIsCreatingNotebook(false)}
                className="text-gray-500 hover:text-gray-700"
              >
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  className="h-6 w-6"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M6 18L18 6M6 6l12 12"
                  />
                </svg>
              </button>
            </div>

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Notebook Name
                </label>
                <input
                  type="text"
                  placeholder="Enter notebook name..."
                  value={newNotebookName}
                  onChange={(e) => setNewNotebookName(e.target.value)}
                  className="w-full border rounded-md p-2 focus:ring-2 focus:ring-primary focus:border-transparent"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Wikipedia Category
                </label>
                <input
                  type="text"
                  placeholder="e.g., 'Category:Artificial_intelligence'"
                  value={categoryPage}
                  onChange={(e) => setCategoryPage(e.target.value)}
                  className="w-full border rounded-md p-2 focus:ring-2 focus:ring-primary focus:border-transparent"
                />
                <p className="mt-1 text-sm text-gray-500">
                  Enter a Wikipedia category to import related articles
                </p>
              </div>
            </div>

            <div className="mt-6 flex justify-end space-x-3">
              <button
                onClick={() => setIsCreatingNotebook(false)}
                className="px-4 py-2 border rounded-md hover:bg-gray-100 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleCreateNotebook}
                disabled={!newNotebookName || !categoryPage}
                className={`px-4 py-2 rounded-md text-white transition-colors
                  ${
                    newNotebookName && categoryPage
                      ? "bg-primary hover:bg-primary/90"
                      : "bg-gray-400 cursor-not-allowed"
                  }`}
              />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
