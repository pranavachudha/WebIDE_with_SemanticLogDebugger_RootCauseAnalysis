import { useState, useEffect, useCallback } from 'react';

export const usePyodide = () => {
  const [pyodide, setPyodide] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const loadPyodideInstance = async () => {
      try {
        if (!window.loadPyodide) {
          throw new Error('Pyodide script not found in index.html');
        }
        const instance = await window.loadPyodide({
          indexURL: "https://cdn.jsdelivr.net/pyodide/v0.25.0/full/"
        });
        setPyodide(instance);
        setLoading(false);
      } catch (err) {
        console.error('Failed to load Pyodide:', err);
        setError(err.message);
        setLoading(false);
      }
    };

    loadPyodideInstance();
  }, []);

  const runCode = useCallback(async (code) => {
    if (!pyodide) return { output: '', error: 'Pyodide not loaded' };

    let output = '';
    
    // Redirect stdout to capture print statements
    pyodide.setStdout({
      batched: (text) => {
        output += text + '\n';
      }
    });

    try {
      await pyodide.runPythonAsync(code);
      return { output, error: null };
    } catch (err) {
      return { output, error: err.message };
    }
  }, [pyodide]);

  return { loading, error, runCode };
};
