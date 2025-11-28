import { useState, useEffect, useRef } from 'react';
import { api } from '../api';
import './FileUploader.css';

export default function FileUploader({ conversationId, onFilesChanged }) {
  const [files, setFiles] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState(null);
  const [dragActive, setDragActive] = useState(false);
  const fileInputRef = useRef(null);

  // Load files when conversation changes
  useEffect(() => {
    if (conversationId) {
      loadFiles();
    } else {
      setFiles([]);
    }
  }, [conversationId]);

  const loadFiles = async () => {
    try {
      const data = await api.listFiles(conversationId);
      setFiles(data.files || []);
      if (onFilesChanged) {
        onFilesChanged(data.files || []);
      }
    } catch (err) {
      console.error('Failed to load files:', err);
    }
  };

  const handleFileUpload = async (fileList) => {
    if (!conversationId || !fileList || fileList.length === 0) return;

    setUploading(true);
    setError(null);

    try {
      // Upload files one by one
      for (const file of Array.from(fileList)) {
        try {
          await api.uploadFile(conversationId, file);
        } catch (err) {
          setError(`Failed to upload ${file.name}: ${err.message}`);
          console.error('Upload error:', err);
        }
      }

      // Reload file list
      await loadFiles();
    } finally {
      setUploading(false);
    }
  };

  const handleDeleteFile = async (fileId, fileName) => {
    try {
      await api.deleteFile(conversationId, fileId);
      await loadFiles();
    } catch (err) {
      setError(`Failed to delete ${fileName}: ${err.message}`);
      console.error('Delete error:', err);
    }
  };

  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);

    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleFileUpload(e.dataTransfer.files);
    }
  };

  const handleFileInputChange = (e) => {
    if (e.target.files && e.target.files.length > 0) {
      handleFileUpload(e.target.files);
    }
  };

  const formatFileSize = (bytes) => {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
  };

  return (
    <div className="file-uploader">
      <div className="section-header">
        <span className="file-icon">📎</span>
        <span>Local Files</span>
      </div>

      {error && (
        <div className="error-message">{error}</div>
      )}

      <div
        className={`drop-zone ${dragActive ? 'active' : ''} ${!conversationId ? 'disabled' : ''}`}
        onDragEnter={handleDrag}
        onDragLeave={handleDrag}
        onDragOver={handleDrag}
        onDrop={handleDrop}
        onClick={() => !uploading && conversationId && fileInputRef.current?.click()}
      >
        <input
          ref={fileInputRef}
          type="file"
          multiple
          onChange={handleFileInputChange}
          style={{ display: 'none' }}
          disabled={!conversationId}
        />

        {uploading ? (
          <div className="drop-zone-text">
            <div className="spinner"></div>
            <span>Uploading...</span>
          </div>
        ) : (
          <div className="drop-zone-text">
            <span className="drop-zone-icon">⬆️</span>
            <span>
              {conversationId
                ? 'Drag & drop files here or click to browse'
                : 'Create a conversation first'}
            </span>
            <span className="drop-zone-hint">Max 5MB per file, UTF-8 text files only</span>
          </div>
        )}
      </div>

      {files.length > 0 && (
        <div className="file-list">
          <div className="file-list-header">Uploaded Files ({files.length})</div>
          {files.map((file) => (
            <div key={file.id} className="file-item">
              <div className="file-info">
                <div className="file-name">{file.filename}</div>
                <div className="file-meta">
                  {file.mime_type && (
                    <span className="file-type">{file.mime_type}</span>
                  )}
                  <span className="file-size">{formatFileSize(file.size_bytes)}</span>
                </div>
              </div>
              <button
                className="delete-button"
                onClick={() => handleDeleteFile(file.id, file.filename)}
                title={`Delete ${file.filename}`}
              >
                ×
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
