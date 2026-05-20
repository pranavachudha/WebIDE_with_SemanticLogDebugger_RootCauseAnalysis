const API_URL = 'http://localhost:8000';

export interface ErrorDetails {
  type: string;
  message: string;
  traceback: string;
  line_number: number;
  file_name?: string;
  failing_function?: string;
  call_stack?: Array<{ file: string; line_number: number; function: string }>;
  code_context?: {
    imports: string[];
    surrounding_code: string;
    failing_function: string;
    class_context: string;
    ast_summary: string[];
  };
}

export interface SemanticMatch {
  bug_id: string;
  score: number;
  embedding?: number[];
  metadata: {
    exception_type: string;
    buggy_code: string;
    fixed_code: string;
    rca_summary: string;
    patch?: string;
    project?: string;
    file_path?: string;
    stack_trace?: string;
  };
}

export interface EmbeddingRecord {
  id: string;
  embedding: number[];
  metadata: Record<string, unknown>;
}

export interface EmbeddingsResponse {
  records: EmbeddingRecord[];
}

export interface FeedbackCodeAction {
  title: string;
  reason: string;
  before?: string;
  after?: string;
}

export interface FeedbackPattern {
  bug_id: string;
  project?: string;
  score: number;
  lesson: string;
  file_path?: string;
}

export interface DeveloperFeedback {
  model_name: string;
  model_version: string;
  mode: string;
  headline: string;
  diagnosis: string;
  root_cause: string;
  primary_fix: string;
  severity: string;
  confidence: number;
  location?: {
    file?: string;
    line_number?: number;
    function?: string;
  };
  evidence: string[];
  fix_steps: string[];
  code_actions: FeedbackCodeAction[];
  historical_patterns: FeedbackPattern[];
  prevention: string[];
  validation_checks: string[];
  debug_questions: string[];
  learning_note: string;
}

export interface ExecutionResult {
  success: boolean;
  stdout: string;
  stderr: string;
  traceback: string;
  error: ErrorDetails | null;
  semantic_matches?: SemanticMatch[];
  query_embedding?: number[];
  root_cause_analysis?: string;
  suggested_fix?: string;
  llm_feedback?: DeveloperFeedback;
  similarity_scores?: number[];
  rca?: unknown;
  filename?: string;
  execution_time?: string;
}

export interface TranslationResponse {
  translated_text: string;
  source_language_code: string;
  target_language_code: string;
  request_id?: string | null;
}

export const getEmbeddings = async (): Promise<EmbeddingsResponse> => {
  try {
    const response = await fetch(`${API_URL}/embeddings`);
    if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
    return await response.json();
  } catch (error) {
    console.error('Failed to load embeddings:', error);
    return { records: [] };
  }
};

export const translateFeedback = async (
  text: string,
  targetLanguageCode: string
): Promise<TranslationResponse> => {
  const response = await fetch(`${API_URL}/translate-feedback`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      text,
      target_language_code: targetLanguageCode,
    }),
  });

  if (!response.ok) {
    const errorBody = await response.json().catch(() => null);
    throw new Error(errorBody?.detail || `HTTP error! status: ${response.status}`);
  }

  return await response.json();
};

export const executeCode = async (filename: string, code: string): Promise<ExecutionResult> => {
  try {
    const response = await fetch(`${API_URL}/execute`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ filename, code }),
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    return await response.json();
  } catch (error) {
    console.error('Failed to execute code:', error);
    return {
      success: false,
      stdout: '',
      stderr: String(error),
      traceback: String(error),
      error: {
        type: 'ConnectionError',
        message: 'Failed to connect to the backend execution server.',
        traceback: String(error),
        line_number: -1,
      },
    };
  }
};

export const stopExecution = async (): Promise<{ success: boolean; message?: string }> => {
  try {
    const response = await fetch(`${API_URL}/stop`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
    });
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    const result = await response.json();
    return { success: result.success, message: result.message };
  } catch (error) {
    console.error('Failed to stop execution:', error);
    return { success: false, message: 'Unable to stop execution.' };
  }
};

export const ingestBugsInPy = async (payload: { limit?: number; run_tests?: boolean } = {}) => {
  try {
    const response = await fetch(`${API_URL}/ingest-bugsinpy`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        dataset_path: 'dataset/BugsInPy',
        limit: payload.limit ?? 150,
        run_tests: payload.run_tests ?? false,
      }),
    });
    if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
    return await response.json();
  } catch (error) {
    return { indexed: 0, error: `Failed to ingest BugsInPy: ${String(error)}` };
  }
};

export const streamFeedback = async (
  error: ErrorDetails,
  rca: any,
  similarBugs: SemanticMatch[],
  sourceCode: string,
  onChunk: (text: string) => void,
  onFinish: (feedback: DeveloperFeedback) => void,
  model?: string
): Promise<void> => {
  try {
    const response = await fetch(`${API_URL}/stream-feedback`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        error,
        rca,
        similar_bugs: similarBugs,
        source_code: sourceCode,
        model,
      }),
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    if (!response.body) {
      throw new Error('ReadableStream not supported by browser or backend response.');
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let accumulatedText = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      const chunk = decoder.decode(value, { stream: true });
      accumulatedText += chunk;

      if (accumulatedText.includes('[METADATA_SEPARATOR]')) {
        const parts = accumulatedText.split('[METADATA_SEPARATOR]');
        const streamingText = parts[0];
        const jsonText = parts[1];

        onChunk(streamingText);

        if (jsonText.trim()) {
          try {
            const parsed = JSON.parse(jsonText.trim());
            onFinish(parsed);
          } catch (e) {
            console.error('Failed to parse final metadata JSON:', e);
          }
        }
      } else {
        onChunk(accumulatedText);
      }
    }
  } catch (err) {
    console.error('Failed to stream feedback:', err);
    onChunk(`Streaming error: ${String(err)}. Fallback initialized.`);
    const fallback: DeveloperFeedback = {
      model_name: 'FallbackEngine',
      model_version: '1.0',
      mode: 'fallback',
      headline: `${error.type || 'Error'}: ${error.message || 'Failing execution'}`,
      diagnosis: error.traceback || 'No traceback captured.',
      root_cause: error.message || 'Execution failed.',
      primary_fix: 'Review surrounding code context and parameters.',
      severity: 'medium',
      confidence: 0.5,
      evidence: [],
      fix_steps: [],
      code_actions: [],
      historical_patterns: [],
      prevention: [],
      validation_checks: [],
      debug_questions: [],
      learning_note: 'Ensure system requirements and configurations are aligned.',
    };
    onFinish(fallback);
  }
};

