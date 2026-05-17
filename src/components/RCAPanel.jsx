
import React, { useEffect, useMemo, useState } from 'react';
import { GitPullRequestArrow, Network, Sparkles } from 'lucide-react';
import { getEmbeddings } from '../services/api';

const EmptyState = () => (
  <div className="empty-debugger">
    <Sparkles size={28} />
    <h2>Semantic Traceback Debugger</h2>
    <p>Run Python code to capture runtime exceptions, embed traceback context, retrieve BugsInPy matches, and generate RCA.</p>
  </div>
);

const Score = ({ value }) => (
  <span className="score">{Math.max(0, Math.min(1, value || 0)).toFixed(2)}</span>
);

function RCAPanel({ execution, activeTab, onTabChange }) {
  if (!execution) return <EmptyState />;

  if (!execution.error) {
    return (
      <div className="debug-content">
        <div className="success-state">Execution finished successfully. No RCA needed.</div>
      </div>
    );
  }

  const {
    error,
    semantic_matches: matches = [],
    query_embedding = [],
    root_cause_analysis: rca,
    suggested_fix: fix,
    filename,
    execution_time,
  } = execution;
  const [datasetEmbeddings, setDatasetEmbeddings] = useState([]);
  const [loadingEmbeddings, setLoadingEmbeddings] = useState(false);
  const [embeddingsError, setEmbeddingsError] = useState('');
  const [filterText, setFilterText] = useState('');
  const [selectedRecordId, setSelectedRecordId] = useState(null);

  const normalizeVector = (vector) => {
    const norm = Math.sqrt(vector.reduce((sum, value) => sum + value * value, 0));
    return norm > 0 ? vector.map((value) => value / norm) : vector;
  };

  const cosineDistance = (a = [], b = []) => {
    const len = Math.min(a.length, b.length);
    if (len === 0) return 1;
    const na = normalizeVector(a.slice(0, len));
    const nb = normalizeVector(b.slice(0, len));
    const dot = na.reduce((sum, value, index) => sum + value * nb[index], 0);
    return 1 - Math.max(-1, Math.min(1, dot));
  };

  useEffect(() => {
    if (activeTab !== 'embeddings') return;
    if (datasetEmbeddings.length > 0) return;

    let mounted = true;
    setLoadingEmbeddings(true);
    setEmbeddingsError('');

    getEmbeddings()
      .then((result) => {
        if (!mounted) return;
        setDatasetEmbeddings(result.records || []);
      })
      .catch((err) => {
        if (!mounted) return;
        setEmbeddingsError(String(err));
      })
      .finally(() => {
        if (!mounted) return;
        setLoadingEmbeddings(false);
      });

    return () => {
      mounted = false;
    };
  }, [activeTab, datasetEmbeddings.length]);

  const hasQuery = query_embedding.length > 0;
  const embeddingPreview = hasQuery
    ? query_embedding.slice(0, 40).map((value, index) => `${index}:${value.toFixed(4)}`).join(' ')
    : 'No embedding available for this error yet.';

  const selectedRecord = useMemo(
    () => datasetEmbeddings.find((record) => record.id === selectedRecordId) || null,
    [datasetEmbeddings, selectedRecordId],
  );

  const renderRuntimeSummary = () => (
    <div className="explorer-summary">
      <div className="viz-item">
        <span className="viz-item-key">Filename</span>
        <span>{filename || 'main.py'}</span>
      </div>
      <div className="viz-item">
        <span className="viz-item-key">Runtime</span>
        <span>{execution_time || 'N/A'}</span>
      </div>
      <div className="viz-item">
        <span className="viz-item-key">Matches</span>
        <span>{matches.length}</span>
      </div>
      <div className="viz-item">
        <span className="viz-item-key">Embedding dims</span>
        <span>{query_embedding.length}</span>
      </div>
    </div>
  );

  if (activeTab === 'matches') {
    return (
      <div className="debug-content">
        <div className="explorer-toolbar">
          <div>
            <h3>
              <Network size={16} /> Similar Historical Bugs
            </h3>
            <p className="muted-copy">Matches are ranked by semantic relevance to this runtime failure.</p>
          </div>
          <button className="secondary-button" onClick={() => onTabChange('visualization')}>
            View Visualization
          </button>
        </div>
        {renderRuntimeSummary()}
        {matches.length === 0 ? (
          <p className="muted-copy">No indexed match crossed the similarity threshold. Run BugsInPy ingestion or broaden the query context.</p>
        ) : (
          matches.map((match) => (
            <article className="match-card" key={match.bug_id}>
              <header>
                <strong>{match.metadata?.project || 'BugsInPy'} / {match.bug_id}</strong>
                <Score value={match.score} />
              </header>
              <p>{match.metadata?.rca_summary || match.metadata?.exception_type || 'Historical bug record'}</p>
              <code>{match.metadata?.file_path || match.metadata?.exception_type}</code>
            </article>
          ))
        )}
      </div>
    );
  }

  if (activeTab === 'patch') {
    const best = matches[0]?.metadata;
    return (
      <div className="debug-content">
        <div className="explorer-toolbar">
          <div>
            <h3>
              <GitPullRequestArrow size={16} /> Retrieved Patch Differences
            </h3>
            <p className="muted-copy">Inspect the buggy and fixed code snippets from the best matching historical bug.</p>
          </div>
          <button className="secondary-button" onClick={() => onTabChange('matches')}>
            Back to Matches
          </button>
        </div>
        {renderRuntimeSummary()}
        {best ? (
          <>
            <div className="patch-grid">
              <div>
                <span>Buggy code</span>
                <pre>{best.buggy_code || 'No buggy hunk available.'}</pre>
              </div>
              <div>
                <span>Fixed code</span>
                <pre>{best.fixed_code || 'No fixed hunk available.'}</pre>
              </div>
            </div>
            <pre className="patch-block">{best.patch || 'Patch body unavailable.'}</pre>
          </>
        ) : (
          <p className="muted-copy">Patch diffs appear after semantic retrieval finds a BugsInPy record.</p>
        )}
      </div>
    );
  }

  if (activeTab === 'visualization') {
    const projectedPoints = [];
    if (query_embedding.length >= 2) {
      projectedPoints.push({ id: 'query', x: query_embedding[0], y: query_embedding[1], color: '#3fb950', radius: 10, isQuery: true });
    }

    const scoreColor = (score) => {
      if (score >= 0.85) return '#38bdf8';
      if (score >= 0.7) return '#8b5cf6';
      if (score >= 0.55) return '#fb7185';
      return '#facc15';
    };

    matches.forEach((match, index) => {
      const embedding = match.embedding;
      let x = 0;
      let y = 0;

      if (embedding && embedding.length >= 2) {
        x = embedding[0];
        y = embedding[1];
      } else {
        x = -0.8 + index * 0.3;
        y = -0.6 + ((index % 3) * 0.4);
      }

      projectedPoints.push({
        id: match.bug_id,
        x,
        y,
        color: scoreColor(match.score),
        radius: 6,
        isQuery: false,
      });
    });

    const hasPlot = projectedPoints.length > 0;
    const xValues = projectedPoints.map((point) => point.x);
    const yValues = projectedPoints.map((point) => point.y);
    const minX = Math.min(...xValues, -1.1);
    const maxX = Math.max(...xValues, 1.1);
    const minY = Math.min(...yValues, -1.1);
    const maxY = Math.max(...yValues, 1.1);
    const padding = 28;
    const width = 400;
    const height = 260;

    const mapX = (value) =>
      ((value - minX) / Math.max(1e-6, maxX - minX)) * (width - padding * 2) + padding;
    const mapY = (value) =>
      height - (((value - minY) / Math.max(1e-6, maxY - minY)) * (height - padding * 2) + padding);

    const plotPoints = projectedPoints.map((point) => ({
      ...point,
      cx: mapX(point.x),
      cy: mapY(point.y),
    }));

    const tracebackText = error.traceback || `${error.type}: ${error.message}`;

    return (
      <div className="debug-content">
        <h3>
          <Network size={16} /> Vector Search Visualization
        </h3>
        <div className="viz-legend">
          <div><span className="legend-dot query" /> Your error</div>
          <div><span className="legend-dot high" /> High similarity</div>
          <div><span className="legend-dot medium" /> Medium similarity</div>
          <div><span className="legend-dot low" /> Low similarity</div>
        </div>
        <div className="viz-grid">
          <div className="viz-card">
            <h4>Error logs</h4>
            <pre className="log-red">{tracebackText}</pre>
          </div>
          <div className="viz-card">
            <h4>Embedding preview</h4>
            <pre className="code-green">{embeddingPreview}</pre>
            {query_embedding.length > 40 && (
              <small className="muted-copy">Showing first 40 dimensions of {query_embedding.length} total.</small>
            )}
          </div>
        </div>
        <div className="scatter-plot">
          <svg viewBox="0 0 400 260" preserveAspectRatio="none">
            <rect x="0" y="0" width="400" height="260" fill="#090c10" rx="12" />
            {hasPlot && plotPoints.map((point) => (
              <circle
                key={point.id}
                cx={point.cx}
                cy={point.cy}
                r={point.radius}
                fill={point.color}
                stroke={point.isQuery ? '#ffffff' : 'transparent'}
                strokeWidth={point.isQuery ? 2 : 0}
              />
            ))}
            {hasPlot && plotPoints.filter((p) => !p.isQuery).map((point) => (
              <line
                key={`line-${point.id}`}
                x1={plotPoints.find((p) => p.isQuery)?.cx || 200}
                y1={plotPoints.find((p) => p.isQuery)?.cy || 130}
                x2={point.cx}
                y2={point.cy}
                stroke={point.color}
                strokeWidth="1"
                opacity="0.35"
              />
            ))}
          </svg>
        </div>
        <div className="viz-actions">
          <button className="secondary-button" onClick={() => onTabChange('embeddings')}>
            Open Embedding Explorer
          </button>
        </div>
      </div>
    );
  }

  if (activeTab === 'embeddings') {
    const filteredEmbeddings = datasetEmbeddings.filter((record) => {
      const query = filterText.toLowerCase();
      return (
        record.id.toLowerCase().includes(query) ||
        JSON.stringify(record.metadata || {}).toLowerCase().includes(query)
      );
    });

    const nearestMatches = hasQuery
      ? filteredEmbeddings
          .map((record) => ({
            ...record,
            distance: cosineDistance(query_embedding, record.embedding),
          }))
          .sort((a, b) => a.distance - b.distance)
          .slice(0, 5)
      : [];

    const selectedRecord = selectedRecordId
      ? datasetEmbeddings.find((record) => record.id === selectedRecordId)
      : null;

    return (
      <div className="debug-content">
        <div className="explorer-toolbar">
          <div>
            <h3>Embedding Explorer</h3>
            <p className="muted-copy">Browse stored vectors and inspect the closest records for the current runtime error.</p>
          </div>
          <button className="secondary-button" onClick={() => onTabChange('visualization')}>
            Back to Visualization
          </button>
        </div>

        {renderRuntimeSummary()}
        <div className="explorer-summary">
          <div className="viz-item">
            <span className="viz-item-key">Records loaded</span>
            <span>{datasetEmbeddings.length}</span>
          </div>
          <div className="viz-item">
            <span className="viz-item-key">Query embedding</span>
            <span>{hasQuery ? 'Available' : 'Missing'}</span>
          </div>
          {embeddingsError && <p className="muted-copy">Error loading embeddings: {embeddingsError}</p>}
        </div>

        <div className="explorer-grid">
          <div>
            <div className="nearest-block">
              <h4>Closest dataset points</h4>
              <div className="nearest-list">
                {nearestMatches.map((record, index) => (
                  <button
                    key={record.id}
                    className={`nearest-card ${selectedRecordId === record.id ? 'highlighted' : ''}`}
                    onClick={() => setSelectedRecordId(record.id)}
                  >
                    <div>
                      <div className="nearest-rank">#{index + 1}</div>
                      <div className="nearest-id">{record.id}</div>
                      <div className="nearest-meta">{record.metadata?.exception_type || 'Stored record'}</div>
                    </div>
                    <div className="nearest-distance">{record.distance.toFixed(3)}</div>
                  </button>
                ))}
              </div>
            </div>

            <div className="soft-panel">
              <h4>Embedding preview</h4>
              <pre className="code-green">{embeddingPreview}</pre>
            </div>
          </div>

          <div className="record-detail">
            <h4>Selected record</h4>
            {selectedRecord ? (
              <>
                <div className="detail-row">
                  <span>ID</span>
                  <strong>{selectedRecord.id}</strong>
                </div>
                <div className="detail-row">
                  <span>Exception</span>
                  <strong>{selectedRecord.metadata?.exception_type || 'Unknown'}</strong>
                </div>
                <div className="detail-row">
                  <span>Project</span>
                  <strong>{selectedRecord.metadata?.project || 'Unknown'}</strong>
                </div>
                <div className="detail-row">
                  <span>Distance</span>
                  <strong>{hasQuery ? cosineDistance(query_embedding, selectedRecord.embedding).toFixed(3) : 'N/A'}</strong>
                </div>
                <div className="detail-text">
                  <pre>{JSON.stringify(selectedRecord.metadata || {}, null, 2)}</pre>
                </div>
              </>
            ) : (
              <p className="muted-copy">Select a record to inspect its stored metadata and embedding details.</p>
            )}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="debug-content">
      <div className="rca-summary-card">
        <div>
          <h3>Root Cause Analysis</h3>
          <p>{rca || 'No root cause summary available yet.'}</p>
        </div>
        <div>
          <span className="chip">{error.type}</span>
          <span className="chip">Line {error.line_number}</span>
        </div>
      </div>
      <div className="row-cards">
        <div className="info-card">
          <h4>Error details</h4>
          <p>{error.message}</p>
          <small>{error.file_name}</small>
        </div>
        <div className="info-card">
          <h4>Suggested fix</h4>
          <p>{fix || 'No fix suggestion available.'}</p>
        </div>
      </div>
      {renderRuntimeSummary()}
      <div className="insight-panel">
        <h4>Semantic Insight</h4>
        <p>{error.traceback ? error.traceback.split('\n').slice(-1)[0] : 'Traceback will appear here once the code is executed.'}</p>
      </div>
    </div>
  );
}

export default RCAPanel;
