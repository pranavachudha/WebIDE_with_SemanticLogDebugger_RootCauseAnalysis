import React, { useEffect, useMemo, useRef, useState } from 'react';
import Editor from '@monaco-editor/react';
import {
  AlertTriangle,
  Bug,
  ChevronRight,
  Download,
  Edit2,
  FileCode,
  Lightbulb,
  Network,
  Play,
  RotateCcw,
  Settings,
  TerminalSquare,
  UploadCloud,
  X,
  Plus,
} from 'lucide-react';

import * as d3 from 'd3';

import RCAPanel from './components/RCAPanel';

import {
  executeCode,
  ingestBugsInPy,
  stopExecution,
  getEmbeddings,
} from './services/api';

const DEFAULT_CODE = `import requests

def fetch_profile(user):
    cache = {"admin": {"name": "Ada", "roles": ["owner"]}}
    profile = cache.get(user)
    return profile["roles"][0]

print("Semantic debugger demo")
print(fetch_profile("guest"))
`;

const DEFAULT_FILES = [
  { id: 'main', name: 'main.py', content: DEFAULT_CODE, dirty: false },
  {
    id: 'imports',
    name: 'missing_import.py',
    content: 'import numpyx\\n\\nprint(numpyx.array([1, 2, 3]))\\n',
    dirty: false,
  },
  {
    id: 'none',
    name: 'none_attribute.py',
    content:
      'def normalize(items):\\n    items.append("ready")\\n    return items\\n\\nprint(normalize(None))\\n',
    dirty: false,
  },
];

const DEBUG_TABS = [
  { key: 'rca', label: 'RCA' },
  { key: 'visualization', label: 'Visualization' },
  { key: 'embeddings', label: 'Embedding Explorer' },
  { key: 'matches', label: 'Matches' },
  { key: 'patch', label: 'Patch' },
];

const PANEL_BUTTONS = [
  { key: 'explorer', label: 'Explorer', icon: FileCode },
  { key: 'run', label: 'Run', icon: Play },
  { key: 'debug', label: 'Debug', icon: Bug },
  { key: 'terminal', label: 'Terminal', icon: TerminalSquare },
  { key: 'semantic', label: 'Semantic RCA', icon: Lightbulb },
  { key: 'vector', label: 'Vector', icon: Network },
  { key: 'upload', label: 'Upload', icon: UploadCloud },
  { key: 'download', label: 'Download', icon: Download },
  { key: 'settings', label: 'Settings', icon: Settings },
];

const panelTitles = {
  explorer: 'File Explorer',
  run: 'Run Workspace',
  debug: 'Debugger',
  terminal: 'Terminal',
  semantic: 'Semantic RCA',
  vector: 'Vector Analytics',
  settings: 'Settings',
};

function App() {
  const [files, setFiles] = useState(DEFAULT_FILES);
  const [activeFileId, setActiveFileId] = useState('main');

  const [activePanel, setActivePanel] = useState('explorer');
  const [activeTab, setActiveTab] = useState('rca');

  const [consoleLines, setConsoleLines] = useState([
    {
      type: 'muted',
      text: 'Ready. Run code to capture traceback and semantic RCA.',
    },
  ]);

  const [execution, setExecution] = useState(null);
  const [isExecuting, setIsExecuting] = useState(false);

  const [isIndexing, setIsIndexing] = useState(false);
  const [uploadError, setUploadError] = useState('');

  const [isCreatingFile, setIsCreatingFile] = useState(false);
  const [newFileName, setNewFileName] = useState('');

  const [isVectorOpen, setIsVectorOpen] = useState(false);

  const editorRef = useRef(null);
  const decorationsRef = useRef([]);
  const uploadInputRef = useRef(null);

  const activeFile = useMemo(
    () => files.find((file) => file.id === activeFileId) || files[0],
    [files, activeFileId]
  );

  const activePanelName = panelTitles[activePanel] || 'Editor';

  const updateEditorDecorations = (lineNumber = -1) => {
    const editor = editorRef.current;

    if (!editor) return;

    decorationsRef.current = editor.deltaDecorations(
      decorationsRef.current,
      lineNumber > 0
        ? [
            {
              range: {
                startLineNumber: lineNumber,
                startColumn: 1,
                endLineNumber: lineNumber,
                endColumn: 1,
              },
              options: {
                isWholeLine: true,
                className: 'failing-line',
                glyphMarginClassName: 'failing-glyph',
              },
            },
          ]
        : []
    );

    if (lineNumber > 0) {
      editor.revealLineInCenter(lineNumber);
    }
  };

  const updateFileContent = (newContent) => {
    setFiles((prev) =>
      prev.map((file) =>
        file.id === activeFileId
          ? { ...file, content: newContent || '', dirty: true }
          : file
      )
    );
  };

  const handleRun = async () => {
    if (isExecuting) return;

    setActivePanel('run');
    setIsExecuting(true);

    setExecution(null);

    setConsoleLines([
      { type: 'muted', text: `python ${activeFile.name}` },
    ]);

    const result = await executeCode(
      activeFile.name,
      activeFile.content
    );

    setExecution(result);

    if (result.success) {
      setActivePanel('run');
      setActiveTab('visualization');

      updateEditorDecorations(-1);

      const stdoutLines = (result.stdout || '')
        .split('\n')
        .filter(Boolean)
        .map((text) => ({
          type: 'stdout',
          text,
        }));

      const stderrLines = (result.stderr || '')
        .split('\n')
        .filter(Boolean)
        .map((text) => ({
          type: 'stderr',
          text,
        }));

      const lines = stdoutLines.length
        ? stdoutLines
        : [
            {
              type: 'stdout',
              text: 'Process completed with no output.',
            },
          ];

      setConsoleLines([
        ...lines,
        ...stderrLines,
        {
          type: 'muted',
          text: `Execution completed in ${
            result.execution_time || 'unknown'
          }.`,
        },
      ]);
    } else {
      setActivePanel('debug');
      setActiveTab('rca');

      updateEditorDecorations(
        result.error?.line_number || -1
      );

      const stdoutLines = (result.stdout || '')
        .split('\n')
        .filter(Boolean)
        .map((text) => ({
          type: 'stdout',
          text,
        }));

      const stderrLines = (
        result.stderr ||
        result.traceback ||
        ''
      )
        .split('\n')
        .filter(Boolean)
        .map((text) => ({
          type: 'stderr',
          text,
        }));

      setConsoleLines([
        ...stdoutLines,
        ...stderrLines,
        {
          type: 'stderr',
          text: `${
            result.error?.type || 'Error'
          }: ${
            result.error?.message || 'Unknown failure'
          }`,
        },
        {
          type: 'muted',
          text: `Semantic retrieval returned ${
            result.semantic_matches?.length ?? 0
          } historical matches.`,
        },
      ]);
    }

    setIsExecuting(false);
  };

  const handleIngest = async () => {
    setIsIndexing(true);

    setConsoleLines([
      {
        type: 'muted',
        text: 'Indexing BugsInPy patches into the semantic vector store...',
      },
    ]);

    const result = await ingestBugsInPy({
      limit: 150,
      run_tests: false,
    });

    setConsoleLines([
      {
        type: result.error ? 'stderr' : 'stdout',
        text:
          result.error ||
          `Indexed ${result.indexed} BugsInPy bug records.`,
      },
      {
        type: 'muted',
        text: 'Run code again to retrieve against the refreshed historical bug index.',
      },
    ]);

    setIsIndexing(false);
  };

  const sendFileToDownload = () => {
    const blob = new Blob([activeFile.content], {
      type: 'text/plain;charset=utf-8',
    });

    const url = URL.createObjectURL(blob);

    const anchor = document.createElement('a');

    anchor.href = url;
    anchor.download = activeFile.name || 'main.py';

    document.body.appendChild(anchor);

    anchor.click();

    document.body.removeChild(anchor);

    URL.revokeObjectURL(url);
  };

  const handleUploadFiles = async (fileList) => {
    const accepted = Array.from(fileList).filter((file) =>
      file.name.toLowerCase().endsWith('.py')
    );

    if (accepted.length === 0) {
      setUploadError('Only .py files are accepted.');
      return;
    }

    setUploadError('');

    for (const file of accepted) {
      const text = await file.text();

      const id = `upload-${Date.now()}-${file.name}`;

      const newFile = {
        id,
        name: file.name,
        content: text,
        dirty: false,
      };

      setFiles((prev) => [...prev, newFile]);

      setActiveFileId(id);
      setActivePanel('explorer');
    }
  };

  const handleUploadSelection = (event) => {
    const fileList = event.target.files;

    if (!fileList) return;

    handleUploadFiles(fileList);

    event.target.value = '';
  };

  const handleDrop = (event) => {
    event.preventDefault();

    if (!event.dataTransfer) return;

    handleUploadFiles(event.dataTransfer.files);
  };

  const handleDragOver = (event) => {
    event.preventDefault();
  };

  const handleCreateFile = () => {
    setIsCreatingFile(true);
    setNewFileName('');
  };

  const confirmCreateFile = () => {
    if (!newFileName.trim()) {
      setIsCreatingFile(false);
      return;
    }

    let finalName = newFileName.trim();

    if (!finalName.endsWith('.py')) {
      finalName += '.py';
    }

    const newId = Date.now().toString();

    const newFile = {
      id: newId,
      name: finalName,
      content: '# New Python file\n',
      dirty: false,
    };

    setFiles((prev) => [...prev, newFile]);

    setActiveFileId(newId);

    setIsCreatingFile(false);
    setNewFileName('');
  };

  const handleNewFileKeyDown = (e) => {
    if (e.key === 'Enter') {
      confirmCreateFile();
    } else if (e.key === 'Escape') {
      setIsCreatingFile(false);
    }
  };

  const renameFile = (fileId) => {
    const file = files.find((item) => item.id === fileId);

    if (!file) return;

    const newName = window.prompt(
      'Rename file',
      file.name
    );

    if (!newName || !newName.trim()) return;

    if (!newName.toLowerCase().endsWith('.py')) {
      window.alert('Filename must end with .py');
      return;
    }

    setFiles((prev) =>
      prev.map((item) =>
        item.id === fileId
          ? { ...item, name: newName.trim() }
          : item
      )
    );
  };

  const deleteFile = (fileId) => {
    if (files.length === 1) return;

    const updated = files.filter(
      (file) => file.id !== fileId
    );

    setFiles(updated);

    if (
      activeFileId === fileId &&
      updated.length > 0
    ) {
      setActiveFileId(updated[0].id);
    }
  };

  const stopRunningExecution = async () => {
    const result = await stopExecution();

    setConsoleLines((prev) => [
      ...prev,
      {
        type: result.success ? 'stdout' : 'stderr',
        text:
          result.message ||
          'Stop request completed.',
      },
    ]);

    setIsExecuting(false);
  };

  const renderPanelContent = () => {
    if (activePanel === 'explorer') {
      return (
        <div
          className="file-section"
          style={{ flex: 1 }}
        >
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              marginBottom: '1rem',
              padding: '0 0.5rem',
            }}
          >
            <span
              style={{
                fontSize: '0.75rem',
                fontWeight: 600,
                color: 'var(--text-secondary)',
                textTransform: 'uppercase',
              }}
            >
              Explorer
            </span>

            <button
              onClick={handleCreateFile}
              className="btn-icon"
              title="New File"
            >
              <Plus size={14} />
            </button>
          </div>

          {execution && (
            <div
              className="explorer-summary"
              style={{ marginTop: '1rem' }}
            >
              <div className="viz-item">
                <span className="viz-item-key">
                  Last file
                </span>

                <span>
                  {execution.filename ||
                    activeFile.name}
                </span>
              </div>
            </div>
          )}

          {isCreatingFile && (
            <div className="file-item new-file-input-wrapper">
              <FileCode size={16} />

              <input
                type="text"
                autoFocus
                value={newFileName}
                onChange={(e) =>
                  setNewFileName(e.target.value)
                }
                onKeyDown={handleNewFileKeyDown}
                onBlur={() =>
                  setIsCreatingFile(false)
                }
                placeholder="filename.py"
                className="new-file-input"
                style={{
                  flex: 1,
                  background: 'transparent',
                  border: 'none',
                  color: 'inherit',
                  outline: 'none',
                  fontFamily: 'inherit',
                  fontSize: 'inherit',
                }}
              />
            </div>
          )}
        </div>
      );
    }

    if (activePanel === 'terminal') {
      return (
        <div className="panel-empty">
          <h3>Terminal</h3>

          <p>
            All program output is captured below,
            including stdout, stderr, and traceback
            details.
          </p>

          <div
            className="terminal-output"
            style={{
              marginTop: '1rem',
              minHeight: '260px',
            }}
          >
            {consoleLines.length === 0 ? (
              <span style={{ opacity: 0.45 }}>
                Run the code to see output...
              </span>
            ) : (
              consoleLines.map((line, index) => (
                <div
                  key={index}
                  className={line.type}
                >
                  {line.text}
                </div>
              ))
            )}
          </div>
        </div>
      );
    }

    if (activePanel === 'settings') {
      return (
        <div className="panel-empty">
          <h3>Settings & Shortcuts</h3>

          <ul
            style={{
              listStyle: 'none',
              paddingLeft: 0,
              marginTop: '1rem',
            }}
          >
            <li>Ctrl+Enter — Run</li>
            <li>Ctrl+O — Upload</li>
            <li>Ctrl+S — Download current file</li>
            <li>
              Ctrl+Shift+D — Download file
            </li>
            <li>
              Ctrl+Shift+V — Open vector
              visualization
            </li>
          </ul>
        </div>
      );
    }

    if (
      activePanel === 'debug' ||
      activePanel === 'semantic'
    ) {
      return (
        <RCAPanel
          execution={execution}
          activeTab={activeTab}
          onTabChange={setActiveTab}
        />
      );
    }

    return (
      <div className="panel-empty">
        <h3>
          {panelTitles[activePanel] ||
            'Workspace'}
        </h3>

        <p>
          Use the left sidebar to open panels,
          upload files, or launch the semantic
          debugger.
        </p>
      </div>
    );
  };

  const selectPanel = (panelKey) => {
    if (panelKey === 'upload') {
      uploadInputRef.current?.click();
      return;
    }

    if (panelKey === 'download') {
      sendFileToDownload();
      return;
    }

    if (panelKey === 'vector') {
      setActivePanel('vector');
      setIsVectorOpen(true);
      return;
    }

    if (panelKey === 'semantic') {
      setActivePanel('semantic');
      setActiveTab('matches');
      return;
    }

    setActivePanel(panelKey);
  };

  const onTabClose = (fileId) => {
    deleteFile(fileId);
  };

  useEffect(() => {
    const keyListener = (event) => {
      const isMeta =
        event.ctrlKey || event.metaKey;

      if (!isMeta) return;

      const key = event.key.toLowerCase();

      if (key === 'enter') {
        event.preventDefault();
        handleRun();
      }

      if (key === 's') {
        event.preventDefault();
        sendFileToDownload();
      }

      if (key === 'o') {
        event.preventDefault();
        uploadInputRef.current?.click();
      }

      if (
        key === 'd' &&
        event.shiftKey
      ) {
        event.preventDefault();
        sendFileToDownload();
      }

      if (
        key === 'v' &&
        event.shiftKey
      ) {
        event.preventDefault();
        setActivePanel('vector');
        setIsVectorOpen(true);
      }
    };

    window.addEventListener(
      'keydown',
      keyListener
    );

    return () =>
      window.removeEventListener(
        'keydown',
        keyListener
      );
  }, [activeFile, isExecuting]);

  return (
    <div className="ide-shell">
      <input
        ref={uploadInputRef}
        type="file"
        accept=".py"
        multiple
        style={{ display: 'none' }}
        onChange={handleUploadSelection}
      />

      <aside className="activity-bar">
        {PANEL_BUTTONS.map((button) => {
          const Icon = button.icon;

          return (
            <button
              key={button.key}
              className={`activity-button ${
                activePanel === button.key
                  ? 'active'
                  : ''
              }`}
              title={button.label}
              onClick={() =>
                selectPanel(button.key)
              }
            >
              <Icon />
            </button>
          );
        })}
      </aside>

      <div
        className="explorer"
        onDrop={handleDrop}
        onDragOver={handleDragOver}
      >
        <div className="brand">
          <FileCode size={20} />

          <div>
            <strong>Semantic IDE</strong>

            <span>
              {panelTitles[activePanel] ||
                'Traceback + Vector Search'}
            </span>
          </div>
        </div>

        <div className="panel-actions">
          <button
            className="secondary-button"
            onClick={handleCreateFile}
          >
            <Play size={14} /> New File
          </button>

          <button
            className="secondary-button"
            onClick={() =>
              uploadInputRef.current?.click()
            }
          >
            <UploadCloud size={14} /> Upload
          </button>
        </div>

        <div className="panel-title">Files</div>

        <div className="file-row-list">
          {files.map((file) => (
            <div
              key={file.id}
              className={`file-row ${
                activeFileId === file.id
                  ? 'selected'
                  : ''
              }`}
            >
              <button
                className="file-row-button"
                onClick={() =>
                  setActiveFileId(file.id)
                }
              >
                <FileCode size={14} />

                <span>{file.name}</span>

                {file.dirty && (
                  <span className="dirty-indicator">
                    ●
                  </span>
                )}
              </button>

              <div className="file-row-actions">
                <button
                  className="icon-button small"
                  onClick={() =>
                    renameFile(file.id)
                  }
                  title="Rename file"
                >
                  <Edit2 size={14} />
                </button>

                <button
                  className="icon-button small"
                  onClick={() =>
                    deleteFile(file.id)
                  }
                  title="Delete file"
                >
                  <X size={14} />
                </button>
              </div>
            </div>
          ))}
        </div>

        <div className="index-card">
          <div>
            <strong>Vector Store</strong>

            <span>
              {execution?.semantic_matches
                ? `${execution.semantic_matches.length} matches`
                : 'No query yet'}
            </span>
          </div>

          <button
            className="secondary-button"
            onClick={handleIngest}
            disabled={isIndexing}
          >
            <RotateCcw size={14} />

            {isIndexing
              ? 'Indexing...'
              : 'Sync BugsInPy'}
          </button>
        </div>

        {uploadError && (
          <div className="error-banner">
            {uploadError}
          </div>
        )}

        <div className="upload-dropzone">
          <p>
            Drag and drop .py files here to upload
            and edit.
          </p>
        </div>
      </div>

      <main className="workspace">
        <header className="topbar">
          <div className="breadcrumbs">
            <span>{activeFile.name}</span>

            <ChevronRight size={14} />

            <span>{activePanelName}</span>
          </div>

          <div className="actions">
            <button
              className="run-button"
              onClick={handleRun}
              disabled={isExecuting}
            >
              <Play size={14} />

              {isExecuting
                ? 'Running...'
                : 'Run'}
            </button>

            <button
              className="secondary-button"
              onClick={stopRunningExecution}
              disabled={!isExecuting}
            >
              <AlertTriangle size={14} /> Stop
            </button>

            <button
              className="secondary-button"
              onClick={sendFileToDownload}
            >
              <Download size={14} /> Download
            </button>
          </div>
        </header>

        <div className="editor-tabs">
          {files.map((file) => (
            <div
              key={file.id}
              className={`editor-tab-button ${
                activeFileId === file.id
                  ? 'active'
                  : ''
              }`}
            >
              <button
                onClick={() =>
                  setActiveFileId(file.id)
                }
              >
                {file.name}

                {file.dirty && (
                  <span className="dirty-indicator">
                    ●
                  </span>
                )}
              </button>

              <button
                className="close-tab"
                onClick={() =>
                  onTabClose(file.id)
                }
              >
                <X size={12} />
              </button>
            </div>
          ))}
        </div>

        <div className="main-grid">
          <section className="editor-area">
            <Editor
              height="100%"
              language="python"
              theme="vs-dark"
              value={activeFile.content}
              onChange={updateFileContent}
              onMount={(editor) => {
                editorRef.current = editor;
              }}
              options={{
                fontSize: 14,
                fontFamily: 'JetBrains Mono',
                minimap: { enabled: false },
                padding: { top: 16 },
                smoothScrolling: true,
                cursorBlinking: 'smooth',
                lineNumbers: 'on',
                renderLineHighlight: 'all',
                automaticLayout: true,
                scrollbar: {
                  vertical: 'visible',
                  horizontal: 'visible',
                  useShadows: false,
                  verticalScrollbarSize: 10,
                  horizontalScrollbarSize: 10,
                },
              }}
            />
          </section>

          <section className="debugger">
            <div className="debug-tabs">
              {DEBUG_TABS.map((tab) => (
                <button
                  key={tab.key}
                  className={
                    activeTab === tab.key
                      ? 'active'
                      : ''
                  }
                  onClick={() => {
                    setActivePanel('debug');
                    setActiveTab(tab.key);
                  }}
                >
                  {tab.label}
                </button>
              ))}
            </div>

            <div className="debug-content">
              {renderPanelContent()}
            </div>
          </section>
        </div>

        <footer className="terminal-container">
          <div className="terminal-header">
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '0.5rem',
              }}
            >
              <TerminalSquare size={14} />

              Console Output
            </div>

            <div className="terminal-actions">
              <button
                className="secondary-button"
                onClick={() =>
                  setConsoleLines([])
                }
              >
                Clear
              </button>
            </div>
          </div>

          <div className="terminal-output">
            {consoleLines.length === 0 ? (
              <span style={{ opacity: 0.45 }}>
                Run the code to see output...
              </span>
            ) : (
              consoleLines.map((line, index) => (
                <div
                  key={index}
                  className={line.type}
                >
                  {line.text}
                </div>
              ))
            )}
          </div>
        </footer>
      </main>

      {isVectorOpen && (
        <VectorModal
          open={isVectorOpen}
          onClose={() =>
            setIsVectorOpen(false)
          }
          execution={execution}
        />
      )}
    </div>
  );
}

function VectorModal({
  open,
  onClose,
  execution,
}) {
  const [nodes, setNodes] = useState([]);
  const [links, setLinks] = useState([]);

  const [loading, setLoading] =
    useState(false);

  const [selected, setSelected] =
    useState(null);

  const [zoom, setZoom] = useState(1);

  const [offset, setOffset] = useState({
    x: 0,
    y: 0,
  });

  const [dragStart, setDragStart] =
    useState(null);

  const normalizeVector = (vector) => {
    const values = Array.isArray(vector)
      ? vector
      : [];

    const norm = Math.sqrt(
      values.reduce(
        (sum, value) => sum + value * value,
        0
      )
    );

    return norm > 0
      ? values.map((value) => value / norm)
      : values;
  };

  const cosineDistance = (
    a = [],
    b = []
  ) => {
    const na = normalizeVector(a);
    const nb = normalizeVector(b);

    if (na.length === 0 || nb.length === 0)
      return Infinity;

    const len = Math.min(
      na.length,
      nb.length
    );

    const dot = na
      .slice(0, len)
      .reduce(
        (sum, value, index) =>
          sum + value * nb[index],
        0
      );

    return (
      1 -
      Math.max(-1, Math.min(1, dot))
    );
  };

  useEffect(() => {
    if (!open) return;

    let mounted = true;

    const load = async () => {
      setLoading(true);

      try {
        const response =
          await getEmbeddings();

        if (!mounted) return;

        const records =
          response.records || [];

        const graphNodes = records
          .filter(
            (record) =>
              Array.isArray(
                record.embedding
              ) &&
              record.embedding.length > 0
          )
          .map((record) => ({
            ...record,
            id: record.id,
            label:
              record.metadata
                ?.exception_type ||
              record.id,
            cluster:
              record.metadata
                ?.exception_type ||
              'Unknown',
            x: 0,
            y: 0,
            embedding:
              record.embedding || [],
          }));

        if (
          execution?.query_embedding
            ?.length
        ) {
          graphNodes.push({
            id: 'query',
            label: 'Runtime Error',
            cluster: 'Current Error',
            embedding:
              execution.query_embedding,
            query: true,
            x: 0,
            y: 0,
          });
        }

        const allNodes = graphNodes;

        const linkCandidates = [];

        for (
          let i = 0;
          i < allNodes.length;
          i += 1
        ) {
          const source = allNodes[i];

          const distances = allNodes
            .map((target, idx) => ({
              target,
              idx,
              distance:
                i === idx
                  ? Infinity
                  : cosineDistance(
                      source.embedding ||
                        [],
                      target.embedding ||
                        []
                    ),
            }))
            .sort(
              (a, b) =>
                a.distance - b.distance
            )
            .slice(0, 2);

          distances.forEach((neighbor) => {
            if (
              Number.isFinite(
                neighbor.distance
              )
            ) {
              linkCandidates.push({
                source: source.id,
                target: neighbor.target.id,
              });
            }
          });
        }

        const width = 1000;
        const height = 600;

        const simulation =
          d3
            .forceSimulation(allNodes)
            .force(
              'charge',
              d3
                .forceManyBody()
                .strength(-120)
            )
            .force(
              'link',
              d3
                .forceLink(linkCandidates)
                .id((node) => node.id)
                .distance(140)
                .strength(0.3)
            )
            .force(
              'center',
              d3.forceCenter(
                width / 2,
                height / 2
              )
            )
            .force(
              'collision',
              d3.forceCollide(32)
            );

        for (
          let i = 0;
          i < 120;
          i += 1
        ) {
          simulation.tick();
        }

        simulation.stop();

        setNodes(
          allNodes.map((node) => ({
            ...node,
            color: node.query
              ? '#3fb950'
              : node.cluster ===
                'Current Error'
              ? '#3fb950'
              : node.cluster ===
                'Unknown'
              ? '#8b949e'
              : '#58a6ff',
            radius: node.query
              ? 16
              : 10,
          }))
        );

        setLinks(linkCandidates);
      } catch (err) {
        console.error(
          'Vector modal load error',
          err
        );
      } finally {
        if (mounted)
          setLoading(false);
      }
    };

    load();

    return () => {
      mounted = false;
    };
  }, [open, execution]);

  const handleZoom = (event) => {
    event.preventDefault();

    const delta =
      event.deltaY > 0 ? -0.1 : 0.1;

    setZoom((current) =>
      Math.max(
        0.4,
        Math.min(2, current + delta)
      )
    );
  };

  const handleMouseDown = (event) => {
    setDragStart({
      x: event.clientX - offset.x,
      y: event.clientY - offset.y,
    });
  };

  const handleMouseMove = (event) => {
    if (!dragStart) return;

    setOffset({
      x: event.clientX - dragStart.x,
      y: event.clientY - dragStart.y,
    });
  };

  const handleMouseUp = () => {
    setDragStart(null);
  };

  const metrics = useMemo(() => {
    const total = nodes.length;

    const clusters = nodes.reduce(
      (acc, node) => {
        const key =
          node.cluster || 'Unknown';

        acc[key] = (acc[key] || 0) + 1;

        return acc;
      },
      {}
    );

    return { total, clusters };
  }, [nodes]);

  if (!open) return null;

  return (
    <div
      className="modal-backdrop"
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUp}
    >
      <div
        className="vector-modal"
        onWheel={handleZoom}
      >
        <div className="vector-header">
          <div>
            <h2>
              Vector Analytics Dashboard
            </h2>

            <p>
              Interactive semantic embedding
              graph of runtime errors and
              historical bug matches.
            </p>
          </div>

          <button
            className="icon-button"
            onClick={onClose}
            title="Close visualization"
          >
            <X size={18} />
          </button>
        </div>

        <div className="vector-body">
          <div className="graph-panel">
            {loading ? (
              <div className="loader-panel">
                Loading vector visualization...
              </div>
            ) : (
              <svg
                className="graph-svg"
                viewBox="0 0 1000 600"
                onMouseDown={
                  handleMouseDown
                }
              >
                <g
                  transform={`translate(${offset.x},${offset.y}) scale(${zoom})`}
                >
                  {links.map((link, idx) => {
                    const source =
                      nodes.find(
                        (node) =>
                          node.id ===
                          link.source
                      );

                    const target =
                      nodes.find(
                        (node) =>
                          node.id ===
                          link.target
                      );

                    if (
                      !source ||
                      !target
                    )
                      return null;

                    return (
                      <line
                        key={`link-${idx}`}
                        x1={source.x}
                        y1={source.y}
                        x2={target.x}
                        y2={target.y}
                        stroke="rgba(92, 178, 255, 0.35)"
                        strokeWidth="1.5"
                      />
                    );
                  })}

                  {nodes.map((node) => (
                    <g
                      key={node.id}
                      transform={`translate(${node.x},${node.y})`}
                    >
                      <circle
                        r={node.radius}
                        fill={node.color}
                        stroke={
                          selected?.id ===
                          node.id
                            ? '#ffffff'
                            : 'rgba(255,255,255,0.15)'
                        }
                        strokeWidth={
                          selected?.id ===
                          node.id
                            ? 2.5
                            : 1
                        }
                        cursor="pointer"
                        onClick={() =>
                          setSelected(node)
                        }
                      />

                      <text
                        x={node.radius + 6}
                        y={4}
                        fill="#c9d1d9"
                        fontSize="12px"
                      >
                        {node.label}
                      </text>
                    </g>
                  ))}
                </g>
              </svg>
            )}
          </div>

          <aside className="vector-sidebar">
            <div className="vector-toolbar">
              <button
                className="secondary-button"
                onClick={() =>
                  setZoom((current) =>
                    Math.min(
                      2,
                      current + 0.2
                    )
                  )
                }
              >
                Zoom In
              </button>

              <button
                className="secondary-button"
                onClick={() =>
                  setZoom((current) =>
                    Math.max(
                      0.4,
                      current - 0.2
                    )
                  )
                }
              >
                Zoom Out
              </button>
            </div>

            <div className="sidebar-card">
              <h4>Analytics</h4>

              <div className="detail-row">
                <span>Nodes</span>

                <strong>
                  {metrics.total}
                </strong>
              </div>

              {Object.entries(
                metrics.clusters
              ).map(([cluster, count]) => (
                <div
                  className="detail-row"
                  key={cluster}
                >
                  <span>{cluster}</span>

                  <strong>{count}</strong>
                </div>
              ))}
            </div>

            <div className="sidebar-card">
              <h4>Selected Node</h4>

              {selected ? (
                <>
                  <div className="detail-row">
                    <span>ID</span>

                    <strong>
                      {selected.id}
                    </strong>
                  </div>

                  <div className="detail-row">
                    <span>Type</span>

                    <strong>
                      {selected.query
                        ? 'Runtime Error'
                        : selected.cluster}
                    </strong>
                  </div>

                  <div className="detail-row">
                    <span>Label</span>

                    <strong>
                      {selected.label}
                    </strong>
                  </div>

                  <pre>
                    {JSON.stringify(
                      selected.metadata ||
                        {},
                      null,
                      2
                    )}
                  </pre>
                </>
              ) : (
                <p className="muted-copy">
                  Click a node to inspect
                  traceback and semantic
                  metadata.
                </p>
              )}
            </div>
          </aside>
        </div>
      </div>
    </div>
  );
}

export default App;