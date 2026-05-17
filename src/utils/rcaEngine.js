
/**
 * Simplified Root Cause Analysis Engine inspired by SemanticLogDebugger
 */

export const analyzeTraceback = (errorMsg) => {
  if (!errorMsg) return null;

  // 1. Parse Traceback
  const frames = parseTraceback(errorMsg);
  if (frames.length === 0) return null;

  // 2. Build Causal Graph (DAG)
  // In a stack trace, the execution flows from the first frame to the last (where it crashed).
  // Root cause is often higher up the stack or a specific semantic pattern.
  const graph = buildGraph(frames);

  // 3. Apply PageRank-like scoring
  // In a stack trace, we give higher weight to frames that are:
  // - Close to the error but not the error itself (potential trigger)
  // - Frames that appear frequently in similar error patterns
  const scores = calculatePageRank(graph);

  // 4. Semantic Matching
  const semanticInsight = getSemanticInsight(errorMsg);

  // 5. Identify Root Cause
  let rootCauseIdx = 0;
  let maxScore = -1;
  scores.forEach((score, idx) => {
    if (score > maxScore) {
      maxScore = score;
      rootCauseIdx = idx;
    }
  });

  return {
    frames,
    rootCauseIdx,
    insight: semanticInsight,
    explanation: generateExplanation(frames[rootCauseIdx], semanticInsight)
  };
};

const parseTraceback = (errorMsg) => {
  const frames = [];
  const lines = errorMsg.split('\n');
  const frameRegex = /File "(.*)", line (\d+), in (.*)/;
  
  lines.forEach(line => {
    const match = line.match(frameRegex);
    if (match) {
      frames.push({
        file: match[1],
        line: parseInt(match[2]),
        func: match[3],
        content: '' // Could be populated if we had the source
      });
    }
  });
  
  // Also try to get the error type and message
  const lastLine = lines[lines.length - 1] || '';
  const errorTypeMatch = lastLine.match(/^(\w+): (.*)/);
  if (errorTypeMatch) {
    frames.errorType = errorTypeMatch[1];
    frames.errorMessage = errorTypeMatch[2];
  }

  return frames;
};

const buildGraph = (frames) => {
  const nodes = frames.map((_, i) => i);
  const edges = [];
  for (let i = 0; i < frames.length - 1; i++) {
    edges.push([i, i + 1]);
  }
  return { nodes, edges };
};

const calculatePageRank = (graph) => {
  const { nodes, edges } = graph;
  if (nodes.length === 0) return [];
  
  // Simplified PageRank for a linear chain:
  // We want to highlight the frame that "triggered" the chain.
  // Often the root cause is 1 or 2 steps before the actual crash.
  const scores = new Array(nodes.length).fill(1 / nodes.length);
  
  // Heuristic: The frame just before the crash (if it's not the crash itself)
  // has a higher probability of being the logical root cause.
  if (nodes.length > 1) {
    scores[nodes.length - 2] = 0.5; // High weight to the penultimate frame
    scores[nodes.length - 1] = 0.2; // The crash itself
    // Distribute remaining
    const remaining = 0.3 / (nodes.length - 2 || 1);
    for (let i = 0; i < nodes.length - 2; i++) {
      scores[i] = remaining;
    }
  }
  
  return scores;
};

const getSemanticInsight = (errorMsg) => {
  const insights = [
    { pattern: /ZeroDivisionError/, title: "Division by Zero", hint: "Check if the denominator is calculated from user input or a variable that could be zero." },
    { pattern: /KeyError/, title: "Missing Dictionary Key", hint: "The key you're looking for doesn't exist. Check if it was deleted or never added." },
    { pattern: /IndexError/, title: "List Index Out of Range", hint: "You're trying to access an element beyond the list length. Verify loop boundaries or empty lists." },
    { pattern: /TypeError/, title: "Incompatible Types", hint: "You're performing an operation on the wrong data type. Ensure variables are converted (e.g., int vs str)." },
    { pattern: /NameError/, title: "Undefined Variable", hint: "A variable name is used before it's assigned. Check for typos in variable names." },
    { pattern: /AttributeError/, title: "Missing Attribute", hint: "The object doesn't have the method or property you're calling. Check if the object is None or of a different class." }
  ];

  for (const insight of insights) {
    if (insight.pattern.test(errorMsg)) {
      return insight;
    }
  }

  return { title: "Unexpected Anomaly", hint: "The system detected an unusual execution flow. Review the highlighted step for logical inconsistencies." };
};

const generateExplanation = (frame, insight) => {
  return `The anomaly was likely triggered in function '${frame.func}' at line ${frame.line}. ${insight.hint}`;
};
