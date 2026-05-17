import React, { useState, useEffect, useCallback, useRef } from 'react';
import Editor from '@monaco-editor/react';
import { 
  Play, 
  Trash2, 
  FileCode, 
  Settings, 
  Terminal as TerminalIcon, 
  Cpu,
  Download,
  Share2,
  Plus,
  FileText,
  X,
  Code
} from 'lucide-react';
import { usePyodide } from './hooks/usePyodide';
import { analyzeTraceback } from './utils/rcaEngine';
import RCAPanel from './components/RCAPanel';

const DEFAULT_FILES = [
  { 
    id: '1', 
    name: 'main.py', 
    content: 'def calculate_ratio(a, b):\n    # This function will trigger a ZeroDivisionError\n    return a / b\n\ndef process_data(val):\n    print(f"Processing value: {val}")\n    return calculate_ratio(val, 0)\n\nprint("🚀 Semantic Debugger Demo Ready")\nprint("Running process_data(10)...")\nprocess_data(10)'
  },
  {
    id: '2',
    name: 'examples.py',
    content: 'def get_user_status(user_id):\n    # This will trigger a KeyError\n    db = {"admin": "active", "guest": "limited"}\n    return db[user_id]\n\nprint("Attempting to fetch status for \"root\"...")\nprint(get_user_status("root"))'
  }
];

const App = () => {
  const [files, setFiles] = useState(DEFAULT_FILES);
  const [activeFileId, setActiveFileId] = useState('1');
  const [isExecuting, setIsExecuting] = useState(false);
  const [rcaResult, setRcaResult] = useState(null);
  const [output, setOutput] = useState([]);
  const [isCreatingFile, setIsCreatingFile] = useState(false);
  const [newFileName, setNewFileName] = useState('');
  const { loading, error: pyodideError, runCode } = usePyodide();
  const terminalEndRef = useRef(null);

  const activeFile = files.find(f => f.id === activeFileId) || files[0];

  useEffect(() => {
    if (terminalEndRef.current) {
      terminalEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [output]);

  // Handle Keyboard Shortcuts
  useEffect(() => {
    const handleKeyDown = (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
        e.preventDefault();
        handleRun();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [activeFile.content, loading, isExecuting]);

  const handleRun = async () => {
    if (loading || isExecuting) return;
    
    setIsExecuting(true);
    setOutput([{ type: 'system', text: 'Executing Python code...' }]);
    
    const result = await runCode(activeFile.content);
    
    if (result.error) {
      setOutput([{ type: 'error', text: result.error }]);
      // Automatically analyze root cause on error
      const analysis = analyzeTraceback(result.error);
      setRcaResult(analysis);
    } else {
      const lines = result.output.split('\n').filter(l => l.trim() !== '');
      setOutput(lines.map(l => ({ type: 'text', text: l })));
      setRcaResult(null);
    }
    setIsExecuting(false);
  };

  const handleManualRCA = () => {
    const errorLine = output.find(l => l.type === 'error');
    if (errorLine) {
      const analysis = analyzeTraceback(errorLine.text);
      setRcaResult(analysis);
    }
  };

  const updateActiveFileContent = (newContent) => {
    setFiles(prev => prev.map(f => 
      f.id === activeFileId ? { ...f, content: newContent || '' } : f
    ));
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
      content: '# New Python file\n'
    };
    
    setFiles([...files, newFile]);
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

  const deleteFile = (e, id) => {
    e.stopPropagation();
    if (files.length === 1) return;
    const newFiles = files.filter(f => f.id !== id);
    setFiles(newFiles);
    if (activeFileId === id) {
      setActiveFileId(newFiles[0].id);
    }
  };

  const clearOutput = () => setOutput([]);

  return (
    <div className="app-container">
      {/* Sidebar */}
      <aside className="sidebar">
        <div className="logo">
          <Cpu size={24} strokeWidth={2.5} />
          <span>PyGlide</span>
        </div>
        
        <div className="file-section" style={{ flex: 1 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem', padding: '0 0.5rem' }}>
            <span style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-secondary)', textTransform: 'uppercase' }}>Explorer</span>
            <button onClick={handleCreateFile} className="btn-icon" title="New File">
              <Plus size={14} />
            </button>
          </div>
          
          <div className="file-list">
            {files.map(file => (
              <div 
                key={file.id} 
                className={`file-item ${activeFileId === file.id ? 'active' : ''}`}
                onClick={() => setActiveFileId(file.id)}
              >
                <FileCode size={16} />
                <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis' }}>{file.name}</span>
                {files.length > 1 && (
                  <button onClick={(e) => deleteFile(e, file.id)} className="close-btn">
                    <X size={12} />
                  </button>
                )}
              </div>
            ))}
            {isCreatingFile && (
              <div className="file-item new-file-input-wrapper">
                <FileCode size={16} />
                <input
                  type="text"
                  autoFocus
                  value={newFileName}
                  onChange={(e) => setNewFileName(e.target.value)}
                  onKeyDown={handleNewFileKeyDown}
                  onBlur={() => setIsCreatingFile(false)}
                  placeholder="filename.py"
                  className="new-file-input"
                  style={{ 
                    flex: 1, 
                    background: 'transparent', 
                    border: 'none', 
                    color: 'inherit', 
                    outline: 'none',
                    fontFamily: 'inherit',
                    fontSize: 'inherit'
                  }}
                />
              </div>
            )}
          </div>
        </div>

        <div className="sidebar-footer">
          <div className="file-item">
            <Settings size={18} />
            <span>Settings</span>
          </div>
        </div>
      </aside>

      {/* Toolbar */}
      <header className="toolbar">
        <div style={{ display: 'flex', gap: '1rem', alignItems: 'center' }}>
          <button 
            className="btn btn-primary" 
            onClick={handleRun} 
            disabled={loading || isExecuting}
          >
            <Play size={16} fill="currentColor" />
            {isExecuting ? 'Running...' : 'Run Code'}
          </button>
          <button className="btn btn-secondary" onClick={clearOutput}>
            <Trash2 size={16} />
            Clear
          </button>
        </div>

        <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
          {!loading && <div className="status-badge">Runtime Ready</div>}
          <div style={{ width: '1px', height: '24px', background: 'var(--border-color)', margin: '0 0.5rem' }}></div>
          <button className="btn btn-secondary" title="Share" style={{ padding: '0.5rem' }}>
            <Share2 size={16} />
          </button>
          <button className="btn btn-secondary" title="Download" style={{ padding: '0.5rem' }}>
            <Download size={16} />
          </button>
        </div>
      </header>

      {/* Editor Area */}
      <main className="editor-container">
        {loading && (
          <div className="loading-overlay">
            <div className="spinner"></div>
            <p>Initializing Python Runtime...</p>
          </div>
        )}
        <Editor
          height="100%"
          defaultLanguage="python"
          theme="vs-dark"
          value={activeFile.content}
          onChange={updateActiveFileContent}
          options={{
            fontSize: 14,
            fontFamily: 'JetBrains Mono',
            minimap: { enabled: false },
            padding: { top: 20 },
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
              horizontalScrollbarSize: 10
            }
          }}
        />
      </main>

      {/* Terminal Area */}
      <footer className="terminal-container">
        <div className="terminal-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <TerminalIcon size={14} />
            Console Output
          </div>
          <div style={{ display: 'flex', gap: '1rem' }}>
             {output.some(l => l.type === 'error') && (
               <button className="btn btn-accent" onClick={handleManualRCA} style={{ padding: '2px 8px', fontSize: '0.65rem' }}>
                 <Cpu size={12} />
                 Debug Root Cause
               </button>
             )}
             {pyodideError && <span style={{ color: 'var(--error)' }}>Runtime Error</span>}
             <span style={{ opacity: 0.5 }}>Python 3.11</span>
          </div>
        </div>
        <div className="terminal-output">
          {output.length === 0 ? (
            <span style={{ opacity: 0.3 }}>Execute code to see output... (Ctrl+Enter)</span>
          ) : (
            output.map((line, i) => (
              <div key={i} className={line.type}>{line.text}</div>
            ))
          )}
          <div ref={terminalEndRef}></div>
        </div>
      </footer>

      {/* RCA Analysis Panel Overlay */}
      <RCAPanel result={rcaResult} onClear={() => setRcaResult(null)} />
    </div>
  );
};

export default App;

