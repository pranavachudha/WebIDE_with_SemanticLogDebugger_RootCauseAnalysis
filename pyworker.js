importScripts("https://cdn.jsdelivr.net/pyodide/v0.25.0/full/pyodide.js");

let pyodideReadyPromise;

async function initPyodide() {
    const pyodide = await loadPyodide({
        indexURL: "https://cdn.jsdelivr.net/pyodide/v0.25.0/full/"
    });
    
    self.printToTerminal = (type, msg) => {
        postMessage({ type, msg });
    };

    await pyodide.runPythonAsync(`
import sys
from js import printToTerminal

class CustomStream:
    def __init__(self, type_name):
        self.type_name = type_name
    def write(self, text):
        if text:
            printToTerminal(self.type_name, text)
    def flush(self):
        pass

sys.stdout = CustomStream('stdout')
sys.stderr = CustomStream('stderr')
    `);
    
    pyodide.setStdin({
        stdin: () => {
            
            // Generate a unique ID for this input request
            const uid = Math.random().toString(36).substring(7);
            
            // Perform a synchronous XHR to the Service Worker
            const xhr = new XMLHttpRequest();
            xhr.open('GET', '/__pyglide_input__?uid=' + uid, false); // false makes it synchronous!
            
            try {
                xhr.send(null);
                if (xhr.status === 200) {
                    return xhr.responseText + '\n';
                }
            } catch(e) {
                console.error("XHR Sync Input Error:", e);
            }
            return '\n';
        }
    });
    
    return pyodide;
}

pyodideReadyPromise = initPyodide();

self.onmessage = async (e) => {
    const pyodide = await pyodideReadyPromise;
    const { id, type, code } = e.data;
    
    if (type === 'run') {
        try {
            // First check for syntax errors / compile
            pyodide.globals.set('__preflight_code__', code);
            await pyodide.runPythonAsync("compile(__preflight_code__, '<user_code>', 'exec')");
            
            // Execute
            await pyodide.runPythonAsync(code);
            postMessage({ type: 'done', id });
        } catch (error) {
            postMessage({ type: 'error', id, error: error.toString() });
        }
    } else if (type === 'repl') {
        try {
            const result = await pyodide.runPythonAsync(code);
            postMessage({ type: 'done', id, result: result !== undefined ? String(result) : undefined });
        } catch (error) {
            postMessage({ type: 'error', id, error: error.toString() });
        }
    }
};
