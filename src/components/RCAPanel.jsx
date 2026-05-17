
import React from 'react';
import { AlertCircle, ArrowDown, GitBranch, Info, Lightbulb } from 'lucide-react';

const RCAPanel = ({ result, onClear }) => {
  if (!result) return null;

  const { frames, rootCauseIdx, insight, explanation } = result;

  return (
    <div className="rca-panel">
      <div className="rca-header">
        <div className="rca-title">
          <AlertCircle size={18} className="icon-error" />
          <span>Root Cause Analysis</span>
        </div>
        <button className="rca-close" onClick={onClear}>✕</button>
      </div>

      <div className="rca-content">
        <div className="rca-summary">
          <div className="rca-insight-card">
            <div className="insight-icon">
              <Lightbulb size={24} />
            </div>
            <div className="insight-text">
              <h3>{insight.title}</h3>
              <p>{explanation}</p>
            </div>
          </div>
        </div>

        <div className="rca-visual-container">
          <h4 className="section-label">Execution Flow (Causal Graph)</h4>
          <div className="causal-graph">
            {frames.map((frame, idx) => (
              <React.Fragment key={idx}>
                <div className={`graph-node ${idx === rootCauseIdx ? 'root-cause' : ''} ${idx === frames.length - 1 ? 'crash-node' : ''}`}>
                  <div className="node-marker"></div>
                  <div className="node-info">
                    <span className="node-func">{frame.func}()</span>
                    <span className="node-loc">Line {frame.line}</span>
                  </div>
                  {idx === rootCauseIdx && <div className="node-badge">Root Cause Identified</div>}
                  {idx === frames.length - 1 && <div className="node-badge error">Crash Point</div>}
                </div>
                {idx < frames.length - 1 && (
                  <div className="graph-edge">
                    <ArrowDown size={14} />
                  </div>
                )}
              </React.Fragment>
            ))}
          </div>
        </div>

        <div className="rca-hint-section">
          <div className="hint-header">
            <Info size={16} />
            <span>Developer Direction</span>
          </div>
          <div className="hint-body">
            {insight.hint}
          </div>
        </div>
      </div>
    </div>
  );
};

export default RCAPanel;
