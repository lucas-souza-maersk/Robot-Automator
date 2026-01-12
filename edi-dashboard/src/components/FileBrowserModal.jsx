import React, { useState, useEffect } from 'react';
import { Modal, List, Button, Input, message, Spin, Tag } from 'antd';
import { FolderOpenFilled, HddFilled, CloudServerOutlined, ArrowUpOutlined, ArrowRightOutlined } from '@ant-design/icons';
import api from '../services/api';

const FileBrowserModal = ({ visible, onCancel, onSelect, initialPath, connectionType, connectionConfig }) => {
  const [currentPath, setCurrentPath] = useState('');
  const [manualPath, setManualPath] = useState('');
  const [items, setItems] = useState([]);
  const [drives, setDrives] = useState([]);
  const [loading, setLoading] = useState(false);

  const isSFTP = connectionType === 'SFTP';

  useEffect(() => {
    if (visible) {
      const startPath = initialPath || (isSFTP ? '/' : '');
      setCurrentPath(startPath);
      setManualPath(startPath);
      
      if (!isSFTP && !startPath) {
        fetchDrives();
      } else {
        browsePath(startPath);
      }
    }
  }, [visible, initialPath, connectionType]);

  const fetchDrives = async () => {
    if (isSFTP) return; // SFTP não tem "Drives", começa no root /
    setLoading(true);
    try {
      const res = await api.get('/system/drives');
      setDrives(res.data);
      setItems([]);
      setCurrentPath('');
      setManualPath('');
    } catch (error) {
      message.error('Failed to load drives');
    } finally {
      setLoading(false);
    }
  };

  const browsePath = async (path) => {
    setLoading(true);
    try {
      let res;
      if (isSFTP) {
        // Modo SFTP: Usa as credenciais do formulário para conectar temporariamente
        if (!connectionConfig.host || !connectionConfig.username) {
            throw new Error("Missing Host or Username configuration.");
        }
        res = await api.post('/sftp/browse', {
            host: connectionConfig.host,
            port: connectionConfig.port || 22,
            username: connectionConfig.username,
            password: connectionConfig.password,
            path: path
        });
      } else {
        // Modo Local
        res = await api.post('/system/browse', { path });
      }

      setItems(res.data);
      setDrives([]);
      setCurrentPath(path);
      setManualPath(path);
    } catch (error) {
      const msg = error.response?.data?.detail || error.message || 'Cannot access folder.';
      message.error(`Error: ${msg}`);
    } finally {
      setLoading(false);
    }
  };

  const handleManualGo = () => {
    if (!manualPath && !isSFTP) fetchDrives();
    else browsePath(manualPath);
  };

  const handleItemClick = (item) => {
    browsePath(item.path);
  };

  const handleDriveClick = (drive) => {
    browsePath(drive);
  };

  const goUp = () => {
    if ((!currentPath || currentPath.length <= 3) && !isSFTP) {
      fetchDrives();
      return;
    }
    if (currentPath === '/' && isSFTP) return;

    const parts = currentPath.split(/[/\\]/);
    if (parts[parts.length - 1] === '') parts.pop();
    parts.pop();
    
    let newPath = parts.join('/') || parts.join('\\');
    
    // SFTP Root fix
    if (isSFTP && newPath === '') newPath = '/';
    
    // Windows Drive fix
    if (!isSFTP && (!newPath || newPath.endsWith(':'))) {
       browsePath(newPath + '/');
    } else {
       browsePath(newPath);
    }
  };

  return (
    <Modal
      title={
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          {isSFTP ? <CloudServerOutlined style={{ color: '#1890ff' }} /> : <HddFilled style={{ color: '#1890ff' }} />}
          <span>{isSFTP ? 'SFTP Browser (Test Connection)' : 'Local/Network Browser'}</span>
          {isSFTP && <Tag color="blue">Connected to {connectionConfig?.host}</Tag>}
        </div>
      }
      open={visible}
      onCancel={onCancel}
      width={700}
      footer={[
        <Button key="back" onClick={onCancel}>Cancel</Button>,
        <Button 
          key="select" 
          type="primary" 
          disabled={!currentPath}
          onClick={() => onSelect(currentPath)}
        >
          Select This Folder
        </Button>
      ]}
    >
      <div style={{ marginBottom: 15, display: 'flex', gap: 8 }}>
        <Button icon={<ArrowUpOutlined />} onClick={goUp} />
        <Input 
          prefix={isSFTP ? <CloudServerOutlined /> : <HddFilled />}
          value={manualPath}
          onChange={(e) => setManualPath(e.target.value)}
          onPressEnter={handleManualGo}
          placeholder={isSFTP ? "/remote/path" : "C:/Path or \\\\Server\\Share"}
        />
        <Button icon={<ArrowRightOutlined />} type="primary" ghost onClick={handleManualGo}>Go</Button>
      </div>

      <div style={{ height: 350, overflowY: 'auto', border: '1px solid #f0f0f0', borderRadius: 4, background: '#fafafa' }}>
        {loading ? (
          <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%', flexDirection: 'column', gap: 10 }}>
            <Spin size="large" />
            <span>{isSFTP ? "Connecting & Listing..." : "Accessing disk..."}</span>
          </div>
        ) : (
          <List
            size="small"
            dataSource={items.length > 0 ? items : drives}
            locale={{ emptyText: "No folders found (or access denied)" }}
            renderItem={(item) => (
              <List.Item 
                style={{ 
                  cursor: 'pointer', 
                  padding: '10px 15px', 
                  borderBottom: '1px solid #f0f0f0'
                }}
                onClick={() => items.length > 0 ? handleItemClick(item) : handleDriveClick(item)}
                onMouseEnter={(e) => e.currentTarget.style.background = '#e6f7ff'}
                onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                  {items.length > 0 ? (
                    <FolderOpenFilled style={{ color: '#faad14', fontSize: '20px' }} />
                  ) : (
                    <HddFilled style={{ color: '#1890ff', fontSize: '20px' }} />
                  )}
                  <span style={{ fontSize: '14px' }}>{items.length > 0 ? item.name : item}</span>
                </div>
              </List.Item>
            )}
          />
        )}
      </div>
    </Modal>
  );
};

export default FileBrowserModal;