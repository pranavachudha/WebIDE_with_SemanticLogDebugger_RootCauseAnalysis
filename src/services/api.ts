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
  similarity_scores?: number[];
  rca?: unknown;
  filename?: string;
  execution_time?: string;
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
