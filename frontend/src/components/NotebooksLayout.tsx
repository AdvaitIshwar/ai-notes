import React, { useState, useEffect } from "react";
import axios from "axios";

interface Note {
  content: string;
  id: string;
  contradicting_info?: ContradictingInfo[];
}

interface Notebook {
  id: string;
  name: string;
  notes: Note[];
}

interface ContradictingInfo {
  text: string;
  score: string;
  wikipedia_link: string;
}

interface RelatedInfo {
  string: string;
  name: string;
  link: string;
  score: number;
}

export default function NotebooksLayout() {
  const [notebooks, setNotebooks] = useState<Notebook[]>([]);
  const [notes, setNotes] = useState<Note[]>([]);
  const [selectedNotebook, setSelectedNotebook] = useState<string | null>(null);
  const [selectedNote, setSelectedNote] = useState<Note | null>(null);
  const [isCreatingNotebook, setIsCreatingNotebook] = useState(false);
  const [newNotebookName, setNewNotebookName] = useState("");
  const [categoryPage, setCategoryPage] = useState("");
  const [relatedInfo, setRelatedInfo] = useState<RelatedInfo[]>([]);
  const [isCreatingNote, setIsCreatingNote] = useState(false);
  const [newNoteContent, setNewNoteContent] = useState("");
  const [isLoadingNote, setIsLoadingNote] = useState(false);

  useEffect(() => {
    fetchNotebooks();
  }, []);

  useEffect(() => {
    if (selectedNotebook) {
      fetchNotes();
    }
  }, [selectedNotebook]);

  const fetchNotebooks = async () => {
    try {
      const response = await axios.get(
        "http://127.0.0.1:5000/get_all_notebooks"
      );
      setNotebooks(response.data);
    } catch (error) {
      console.error("Error fetching notebooks:", error);
    }
  };

  const fetchNotes = async () => {
    const response = await axios.get(
      `http://127.0.0.1:5000/get_notes?notebook_id=${selectedNotebook}`
    );
    console.log(response.data);
    setNotes(response.data);
  };

  const handleCreateNotebook = async () => {
    if (!newNotebookName || !categoryPage) return;

    try {
      await axios.post("http://127.0.0.1:5000/create_notebook", {
        notebook_name: newNotebookName,
        category_page: categoryPage,
      });
      setNewNotebookName("");
      setCategoryPage("");
      fetchNotebooks();
    } catch (error) {
      console.error("Error creating notebook:", error);
    } finally {
      setIsCreatingNotebook(false);
    }
  };

  const handleCreateNote = async () => {
    if (!selectedNotebook || !newNoteContent) return;

    setIsLoadingNote(true);
    try {
      await axios.post("http://127.0.0.1:5000/add_note", {
        notebook_id: selectedNotebook,
        note: newNoteContent,
      });
      setIsCreatingNote(false);
      setNewNoteContent("");
      await fetchNotebooks();
      await fetchNotes();
    } catch (error) {
      console.error("Error creating note:", error);
    } finally {
      setIsLoadingNote(false);
    }
  };

  const getNote = async (noteId: string) => {
    try {
      const response = await axios.get(
        `http://127.0.0.1:5000/get_note?note_id=${noteId}`
      );
      setSelectedNote(response.data);
    } catch (error) {
      console.error("Error fetching note:", error);
    }
  };

  const learnMore = async (noteId: string) => {
    try {
      const response = await axios.get(
        `http://127.0.0.1:5000/learn_more?note_id=${noteId}`
      );
      setRelatedInfo(response.data.results);
      console.log(response.data.results);
    } catch (error) {
      console.error("Error fetching related info:", error);
    }
  };

  // Function to go back to notebooks view
  const backToNotebooks = () => {
    setSelectedNotebook(null);
    setSelectedNote(null);
    setRelatedInfo([]);
  };

  // Function to go back to notes view
  const backToNotes = () => {
    setSelectedNote(null);
    setRelatedInfo([]);
  };

  // Render notebooks grid on main screen
  const renderNotebooksGrid = () => {
    return (
      <div className="p-8">
        <div className="flex justify-between items-center mb-8">
          <h1 className="text-2xl font-bold">My Notebooks</h1>
          <button
            onClick={() => setIsCreatingNotebook(true)}
            className="bg-primary text-white px-4 py-2 rounded-lg hover:bg-primary/90"
          >
            + New Notebook
          </button>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {notebooks.map((notebook) => (
            <button
              key={notebook.id}
              onClick={() => {
                setSelectedNotebook(notebook.id);
              }}
              type="button"
              className="bg-card border rounded-lg p-6 cursor-pointer hover:shadow-md transition-shadow hover:border-primary hover:border-2 text-left"
            >
              <h2 className="text-xl font-semibold mb-2">{notebook.name}</h2>
              <p className="text-muted-foreground">
                {notebook.notes ? notebook.notes.length : 0} notes
              </p>
            </button>
          ))}
        </div>

        {notebooks.length === 0 && (
          <div className="text-center py-16">
            <p className="text-muted-foreground">
              No notebooks yet. Create your first notebook to get started.
            </p>
          </div>
        )}
      </div>
    );
  };

  // Render notes list for a selected notebook
  const renderNotesView = () => {
    if (!selectedNotebook) return null;

    return (
      <div className="p-8">
        <div className="flex items-center mb-8">
          <button
            onClick={backToNotebooks}
            className="mr-4 text-muted-foreground hover:text-foreground"
          >
            Back to Notebooks
          </button>
          <h1 className="text-2xl font-bold">
            {notebooks.find((nb) => nb.id === selectedNotebook)?.name}
          </h1>
        </div>

        {notebooks.find((nb) => nb.id === selectedNotebook)?.notes.length ===
          0 && (
          <div className="text-center py-16">
            <p className="text-muted-foreground">
              This notebook doesn't have any notes yet.
            </p>
          </div>
        )}
      </div>
    );
  };

  // Render selected note with its details
  const renderNoteDetail = () => {
    if (!selectedNote) return null;

    return (
      <div className="p-8">
        <div className="flex items-center mb-8">
          <button
            onClick={backToNotes}
            className="mr-4 text-muted-foreground hover:text-foreground"
          >
            Back to Notes
          </button>
          <h1 className="text-2xl font-bold">Note Details</h1>
        </div>

        <div className="bg-card border rounded-lg p-6 mb-6">
          <p className="text-lg">{selectedNote.content}</p>
        </div>

        {selectedNote.contradicting_info &&
          selectedNote.contradicting_info.length > 0 && (
            <div className="bg-yellow-50 border-yellow-200 border rounded-lg p-6 mb-6">
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

        {relatedInfo.length > 0 ? (
          <div className="bg-gray-50 border border-gray-200 rounded-lg p-6">
            <h3 className="text-lg font-medium mb-4">Related Information</h3>
            <div className="space-y-4">
              {relatedInfo.map((info, index) => (
                <div
                  key={index}
                  className="bg-white rounded-lg p-4 border border-gray-100"
                >
                  <p className="text-gray-800">{info.string}</p>
                  <div className="mt-2 flex justify-between items-center">
                    <span className="text-sm text-gray-600">{info.name}</span>
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
          </div>
        ) : (
          <div className="text-center">
            <button
              onClick={() => learnMore(selectedNote.id)}
              disabled={isLoadingNote}
              className="bg-blue-600 text-white px-6 py-3 rounded-md hover:bg-blue-700 disabled:bg-blue-400"
            >
              {isLoadingNote ? "Loading..." : "Learn More"}
            </button>
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="flex h-screen bg-background">
      {/* Main Content Area */}
      <div className="flex-1 flex">
        {/* Left Panel - Main Content */}
        <div className="flex-1 overflow-y-auto p-8 border-r">
          {!selectedNotebook && renderNotebooksGrid()}
          {selectedNotebook && !selectedNote && renderNotesView()}
          {selectedNote && renderNoteDetail()}
        </div>

        {/* Right Panel - Notes Sidebar */}
        {selectedNotebook && !selectedNote && (
          <div className="w-96 border-l bg-card p-6 overflow-y-auto flex flex-col gap-4">
            <div className="sticky top-0 bg-card pb-4 border-b">
              <button
                onClick={() => setIsCreatingNote(true)}
                className="bg-primary text-primary-foreground px-4 py-2 rounded-lg w-full hover:bg-primary/90 focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2"
              >
                + New Note
              </button>
            </div>
            <div className="flex flex-col gap-3">
              {notebooks
                .find((nb) => nb.id === selectedNotebook)
                ?.notes.map((note) => (
                  <button
                    key={note.id}
                    onClick={() => {
                      setSelectedNote(note);
                      getNote(note.id);
                    }}
                    className="bg-secondary/50 hover:bg-secondary text-secondary-foreground p-4 rounded-lg w-full text-left transition-colors"
                  >
                    <p className="line-clamp-3 text-sm">{note.content}</p>
                    {note.contradicting_info &&
                      note.contradicting_info.length > 0 && (
                        <div className="flex items-center mt-2 text-yellow-500 text-xs">
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
            </div>
          </div>
        )}
      </div>

      {/* Create Notebook Modal */}
      {isCreatingNotebook && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50">
          <div className="bg-card rounded-lg shadow-xl max-w-md w-full p-8">
            <div className="flex justify-between items-center mb-8">
              <h2 className="text-2xl font-semibold">Create New Notebook</h2>
            </div>

            <div className="space-y-6">
              <div>
                <label className="block text-sm font-medium mb-2">
                  Notebook Name
                </label>
                <input
                  type="text"
                  placeholder="Enter notebook name..."
                  value={newNotebookName}
                  onChange={(e) => setNewNotebookName(e.target.value)}
                  className="w-full border rounded-lg p-3 focus:ring-2 focus:ring-primary focus:border-transparent"
                />
              </div>

              <div>
                <label className="block text-sm font-medium mb-2">
                  Wikipedia Category
                </label>
                <input
                  type="text"
                  placeholder="e.g., 'Category:Artificial_intelligence'"
                  value={categoryPage}
                  onChange={(e) => setCategoryPage(e.target.value)}
                  className="w-full border rounded-lg p-3 focus:ring-2 focus:ring-primary focus:border-transparent"
                />
                <p className="mt-2 text-sm text-gray-500">
                  Enter a Wikipedia category to import related articles
                </p>
              </div>
            </div>

            <div className="mt-8 flex justify-end gap-3">
              <button
                onClick={() => setIsCreatingNotebook(false)}
                className="px-4 py-2 border rounded-lg hover:bg-gray-100 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleCreateNotebook}
                disabled={!newNotebookName || !categoryPage || isLoadingNote}
                className={`px-4 py-2 rounded-lg text-white transition-colors ${
                  newNotebookName && categoryPage && !isLoadingNote
                    ? "bg-primary hover:bg-primary/90"
                    : "bg-gray-400 cursor-not-allowed"
                }`}
              >
                {isLoadingNote ? "Creating..." : "Create Notebook"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Create Note Modal */}
      {isCreatingNote && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50">
          <div className="bg-card rounded-lg shadow-xl max-w-2xl w-full p-8">
            <div className="flex justify-between items-center mb-8">
              <h2 className="text-2xl font-semibold">Create New Note</h2>
            </div>

            <div>
              <label className="block text-sm font-medium mb-2">
                Note Content
              </label>
              <textarea
                placeholder="Enter your note..."
                value={newNoteContent}
                onChange={(e) => setNewNoteContent(e.target.value)}
                rows={8}
                className="w-full border rounded-lg p-3 focus:ring-2 focus:ring-primary focus:border-transparent"
              />
            </div>

            <div className="mt-8 flex justify-end gap-3">
              <button
                onClick={() => setIsCreatingNote(false)}
                className="px-4 py-2 border rounded-lg hover:bg-gray-100 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleCreateNote}
                disabled={!newNoteContent || isLoadingNote}
                className={`px-4 py-2 rounded-lg text-white transition-colors flex items-center gap-2
                  ${
                    newNoteContent && !isLoadingNote
                      ? "bg-primary hover:bg-primary/90"
                      : "bg-gray-400 cursor-not-allowed"
                  }`}
              >
                {isLoadingNote ? (
                  <>
                    <svg
                      className="animate-spin h-5 w-5"
                      xmlns="http://www.w3.org/2000/svg"
                      fill="none"
                      viewBox="0 0 24 24"
                    >
                      <circle
                        className="opacity-25"
                        cx="12"
                        cy="12"
                        r="10"
                        stroke="currentColor"
                        strokeWidth="4"
                      ></circle>
                      <path
                        className="opacity-75"
                        fill="currentColor"
                        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                      ></path>
                    </svg>
                    <span>Creating...</span>
                  </>
                ) : (
                  <span>Create Note</span>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
