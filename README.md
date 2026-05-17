# WebIDE with Semantic Log Debugger & Root Cause Analysis

A web-based Integrated Development Environment (IDE) for Python, built with React and Vite. It integrates `pyodide` for in-browser Python execution and features a Semantic Log Debugger and Root Cause Analysis (RCA) engine to analyze and troubleshoot your code execution interactively.

## Prerequisites

Before running the project, make sure you have the following installed:
- [Node.js](https://nodejs.org/) (version 18+ recommended)
- [npm](https://www.npmjs.com/) (comes with Node.js)

## Getting Started

1. **Clone the repository:**
   ```bash
   git clone git@github.com:pranavachudha/WebIDE_with_SemanticLogDebugger_RootCauseAnalysis.git
   cd WebIDE_with_SemanticLogDebugger_RootCauseAnalysis
   ```

2. **Install dependencies:**
   ```bash
   npm install
   ```

3. **Run the development server:**
   ```bash
   npm run dev
   ```

4. Open your browser and navigate to the URL provided in the terminal (usually `http://localhost:5173`).

## Project Structure

- `src/` - Contains the React source code.
  - `hooks/usePyodide.js` - Custom hook for managing Pyodide instance.
  - `utils/rcaEngine.js` - Logic for Root Cause Analysis engine.
- `index.html` - Entry point for the Vite application.
- `package.json` - Project metadata and dependencies.

## Technologies Used

- **React** - UI Library
- **Vite** - Build Tool
- **Pyodide** - Python running in the browser
- **Monaco Editor** - Code editor component
- **Lucide React** - Icon library
