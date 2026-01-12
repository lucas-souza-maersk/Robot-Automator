import React, { useState, useEffect } from 'react';
import { 
  Card, Form, Input, Button, Switch, Select, 
  message, Popconfirm, Row, Col, Divider, Modal, List, InputNumber 
} from 'antd';
import { 
  SaveOutlined, PlusOutlined, DeleteOutlined, 
  FolderOpenOutlined, RobotOutlined, EyeOutlined,
  CloudServerOutlined, HddOutlined, DatabaseOutlined, FileTextOutlined
} from '@ant-design/icons';
import MainLayout from '../components/MainLayout';
import FileBrowserModal from '../components/FileBrowserModal';
import api from '../services/api';
import { useLanguage } from '../contexts/LanguageContext'; // Importando tradução

const { Option } = Select;

const Configuration = () => {
  const { t } = useLanguage(); // Hook de tradução
  const [profiles, setProfiles] = useState({});
  const [activeProfile, setActiveProfile] = useState(null);
  const [loading, setLoading] = useState(false);
  
  // Browser State
  const [browserVisible, setBrowserVisible] = useState(false);
  const [browserField, setBrowserField] = useState(null);
  const [browserConnectionType, setBrowserConnectionType] = useState('local');
  const [browserConfig, setBrowserConfig] = useState({});
  
  // Preview State
  const [previewVisible, setPreviewVisible] = useState(false);
  const [previewFiles, setPreviewFiles] = useState([]);
  const [previewLoading, setPreviewLoading] = useState(false);

  const [form] = Form.useForm();
  
  const sourceType = Form.useWatch(['source', 'type'], form);
  const destType = Form.useWatch(['destination', 'type'], form);
  const backupEnabled = Form.useWatch(['settings', 'backup', 'enabled'], form);

  useEffect(() => {
    loadProfiles();
  }, []);

  const loadProfiles = async () => {
    try {
      const res = await api.get('/profiles');
      setProfiles(res.data);
      const keys = Object.keys(res.data);
      if (keys.length > 0 && !activeProfile) {
        changeActiveProfile(keys[0], res.data);
      }
    } catch (error) {
      message.error('Error loading profiles');
    }
  };

  const changeActiveProfile = (key, data = profiles) => {
    setActiveProfile(key);
    form.resetFields();
    form.setFieldsValue(data[key]);
  };

  const handleSave = async (values) => {
    setLoading(true);
    try {
      const updatedProfile = { ...profiles[activeProfile], ...values };
      const updatedProfiles = { ...profiles, [activeProfile]: updatedProfile };
      await api.post('/profiles', { profiles: updatedProfiles });
      setProfiles(updatedProfiles);
      message.success('Configuration saved successfully');
    } catch (error) {
      message.error('Failed to save configuration');
    } finally {
      setLoading(false);
    }
  };

  const createNewProfile = () => {
    const name = `Profile_${Object.keys(profiles).length + 1}`;
    const newProfile = {
      name: name,
      enabled: false,
      action: 'copy',
      source: { type: 'local', path: '' },
      destination: { type: 'local', path: '' },
      settings: {
        file_format: '*.edi',
        scan_interval: { value: 5, unit: 's' },
        db_path: `C:/EDI_DATA/${name}/db.db`,
        log_path: `C:/EDI_DATA/${name}/logs.log`,
        backup: { enabled: false, path: '' },
        alerting: { enabled: false, webhook_url: '' }
      }
    };
    const updated = { ...profiles, [name]: newProfile };
    setProfiles(updated);
    changeActiveProfile(name, updated);
  };

  const deleteProfile = async () => {
    const updated = { ...profiles };
    delete updated[activeProfile];
    try {
      await api.post('/profiles', { profiles: updated });
      setProfiles(updated);
      const keys = Object.keys(updated);
      if (keys.length > 0) changeActiveProfile(keys[0], updated);
      else setActiveProfile(null);
      message.success('Profile deleted');
    } catch (error) {
      message.error('Error deleting profile');
    }
  };

  // --- File Browser Logic ---
  const openBrowser = (fieldIdentifier, type = 'local', sectionPrefix = null) => {
    setBrowserField(fieldIdentifier);
    setBrowserConnectionType(type);

    if (type === 'SFTP' && sectionPrefix) {
        const config = form.getFieldValue(sectionPrefix); 
        if (!config || !config.host || !config.username) {
            return message.warning('Please fill Host and Username before browsing.');
        }
        setBrowserConfig(config);
    } else {
        setBrowserConfig({});
    }

    setBrowserVisible(true);
  };

  const handleBrowserSelect = (path) => {
    if (!browserField) return;

    if (browserField === 'source') form.setFieldValue(['source', 'path'], path);
    else if (browserField === 'source_remote') form.setFieldValue(['source', 'remote_path'], path);
    else if (browserField === 'destination') form.setFieldValue(['destination', 'path'], path);
    else if (browserField === 'destination_remote') form.setFieldValue(['destination', 'remote_path'], path);
    else if (browserField === 'backup') form.setFieldValue(['settings', 'backup', 'path'], path);
    else if (browserField === 'db') form.setFieldValue(['settings', 'db_path'], path + '/db.db');
    else if (browserField === 'log') form.setFieldValue(['settings', 'log_path'], path + '/logs.log');

    setBrowserVisible(false);
  };

  const getInitialBrowserPath = () => {
    if (browserField === 'source') return form.getFieldValue(['source', 'path']);
    if (browserField === 'source_remote') return form.getFieldValue(['source', 'remote_path']);
    if (browserField === 'destination') return form.getFieldValue(['destination', 'path']);
    if (browserField === 'destination_remote') return form.getFieldValue(['destination', 'remote_path']);
    if (browserField === 'backup') return form.getFieldValue(['settings', 'backup', 'path']);
    if (browserField === 'db') {
        const val = form.getFieldValue(['settings', 'db_path']);
        return val ? val.substring(0, val.lastIndexOf('/')) : '';
    }
    return '';
  };

  const handlePreview = async () => {
    if (form.getFieldValue(['source', 'type']) !== 'local') {
      return message.info('Preview is currently only available for Local/Network paths.');
    }
    const path = form.getFieldValue(['source', 'path']);
    const format = form.getFieldValue(['settings', 'file_format']);

    if (!path) return message.warning('Source path is empty');

    setPreviewLoading(true);
    setPreviewVisible(true);
    try {
      const res = await api.post('/system/preview', { path, pattern: format || '*.*' });
      setPreviewFiles(res.data.files);
    } catch (error) {
      message.error('Preview failed. Check path access.');
      setPreviewFiles([]);
    } finally {
      setPreviewLoading(false);
    }
  };

  // --- Render Helpers ---
  const renderLocationFields = (prefix, type) => {
    const isSFTP = type === 'SFTP';
    
    if (isSFTP) {
      return (
        <>
          <Row gutter={8}>
            <Col span={16}>
              <Form.Item name={[prefix, 'host']} label={t('host_ip')} rules={[{required: true}]}>
                <Input placeholder="192.168.x.x" prefix={<CloudServerOutlined />} />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item name={[prefix, 'port']} label={t('port')}>
                <InputNumber style={{ width: '100%' }} defaultValue={22} />
              </Form.Item>
            </Col>
          </Row>
          <Row gutter={8}>
            <Col span={12}>
              <Form.Item name={[prefix, 'username']} label={t('username')} rules={[{required: true}]}>
                <Input />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name={[prefix, 'password']} label={t('password')}>
                <Input.Password placeholder="Secret" />
              </Form.Item>
            </Col>
          </Row>
          <Form.Item label={t('remote_path')}>
            <Input.Group compact style={{ display: 'flex' }}>
                <Form.Item name={[prefix, 'remote_path']} noStyle rules={[{required: true}]}>
                    <Input style={{ width: 'calc(100% - 32px)' }} placeholder="/home/user/input" />
                </Form.Item>
                <Button 
                    icon={<FolderOpenOutlined />} 
                    onClick={() => openBrowser(`${prefix}_remote`, 'SFTP', prefix)} 
                    title="Browse SFTP Server"
                />
            </Input.Group>
          </Form.Item>
        </>
      );
    }
    
    // Local / SMB
    return (
      <Form.Item label={t('local_path')}>
        <Input.Group compact style={{ display: 'flex' }}>
          <Form.Item name={[prefix, 'path']} noStyle>
            <Input style={{ width: 'calc(100% - 32px)' }} prefix={<HddOutlined />} />
          </Form.Item>
          <Button icon={<FolderOpenOutlined />} onClick={() => openBrowser(prefix, 'local')} />
        </Input.Group>
      </Form.Item>
    );
  };

  if (!activeProfile) return (
    <MainLayout>
      <div style={{ textAlign: 'center', marginTop: 50 }}>
        <Button type="primary" icon={<PlusOutlined />} onClick={createNewProfile}>{t('create_profile')}</Button>
      </div>
    </MainLayout>
  );

  return (
    <MainLayout>
      <div style={{ display: 'flex', gap: 20, height: '100%' }}>
        
        <Card 
          title={t('profiles_list')} 
          style={{ width: 260, height: 'fit-content' }}
          extra={<Button type="dashed" size="small" icon={<PlusOutlined />} onClick={createNewProfile}>{t('new_profile')}</Button>}
        >
          <List
            size="small"
            dataSource={Object.keys(profiles)}
            renderItem={item => (
              <List.Item 
                onClick={() => changeActiveProfile(item)}
                style={{ 
                  cursor: 'pointer', 
                  background: activeProfile === item ? '#e6f7ff' : 'transparent',
                  borderLeft: activeProfile === item ? '3px solid #1890ff' : '3px solid transparent',
                  paddingLeft: 10
                }}
              >
                <span style={{ fontWeight: activeProfile === item ? 600 : 400 }}>
                  <RobotOutlined style={{ marginRight: 8 }} /> {item}
                </span>
              </List.Item>
            )}
          />
        </Card>

        <div style={{ flex: 1, overflowY: 'auto' }}>
          <Form form={form} layout="vertical" onFinish={handleSave}>
            
            <Card style={{ marginBottom: 20 }}>
              <Row justify="space-between" align="middle">
                <Col>
                  <h2 style={{ margin: 0 }}>{t('editing')}: {activeProfile}</h2>
                </Col>
                <Col>
                  <Form.Item name="enabled" valuePropName="checked" noStyle>
                    <Switch checkedChildren={t('active_status')} unCheckedChildren={t('paused_status')} />
                  </Form.Item>
                  <Popconfirm title={t('confirm_delete')} onConfirm={deleteProfile}>
                    <Button danger type="text" icon={<DeleteOutlined />} style={{ marginLeft: 10 }}>{t('delete')}</Button>
                  </Popconfirm>
                </Col>
              </Row>
            </Card>

            <Row gutter={20}>
              <Col span={12}>
                <Card title={t('source_config')} type="inner" style={{ marginBottom: 20 }}>
                  <Form.Item name={['source', 'type']} label={t('source_type')}>
                    <Select>
                      <Option value="local">Local / Network (SMB)</Option>
                      <Option value="SFTP">SFTP / SSH</Option>
                    </Select>
                  </Form.Item>
                  {renderLocationFields('source', sourceType)}
                </Card>
              </Col>

              <Col span={12}>
                <Card title={t('dest_config')} type="inner" style={{ marginBottom: 20 }}>
                  <Form.Item name={['destination', 'type']} label={t('dest_type')}>
                    <Select>
                      <Option value="local">Local / Network (SMB)</Option>
                      <Option value="SFTP">SFTP / SSH</Option>
                    </Select>
                  </Form.Item>
                  {renderLocationFields('destination', destType)}
                  
                  <Form.Item name="action" label={t('post_action')}>
                    <Select>
                      <Option value="copy">{t('copy_action')}</Option>
                      <Option value="move">{t('move_action')}</Option>
                    </Select>
                  </Form.Item>
                </Card>
              </Col>
            </Row>

            <Card title={t('system_settings')} style={{ marginBottom: 20 }}>
              <Row gutter={20}>
                <Col span={12}>
                  <Form.Item label={t('file_pattern')}>
                    <div style={{ display: 'flex', gap: 10 }}>
                      <Form.Item name={['settings', 'file_format']} noStyle>
                        <Input style={{ flex: 1 }} placeholder="*.edi, *.txt" />
                      </Form.Item>
                      <Button icon={<EyeOutlined />} onClick={handlePreview}>{t('preview')}</Button>
                    </div>
                  </Form.Item>
                </Col>
                <Col span={6}>
                   <Form.Item label={t('scan_int')} name={['settings', 'scan_interval', 'value']}>
                     <InputNumber min={1} style={{ width: '100%' }} />
                   </Form.Item>
                </Col>
              </Row>

              <Divider />

              <Row gutter={20}>
                <Col span={12}>
                  <Form.Item label={t('db_path')}>
                    <Input.Group compact style={{ display: 'flex' }}>
                      <Form.Item name={['settings', 'db_path']} noStyle>
                        <Input style={{ width: 'calc(100% - 32px)' }} prefix={<DatabaseOutlined />} />
                      </Form.Item>
                      <Button icon={<FolderOpenOutlined />} onClick={() => openBrowser('db')} />
                    </Input.Group>
                  </Form.Item>
                </Col>
                <Col span={12}>
                  <Form.Item label={t('log_path')}>
                    <Input.Group compact style={{ display: 'flex' }}>
                      <Form.Item name={['settings', 'log_path']} noStyle>
                        <Input style={{ width: 'calc(100% - 32px)' }} prefix={<FileTextOutlined />} />
                      </Form.Item>
                      <Button icon={<FolderOpenOutlined />} onClick={() => openBrowser('log')} />
                    </Input.Group>
                  </Form.Item>
                </Col>
              </Row>

              <Divider dashed />

              <Row gutter={20} align="middle">
                <Col span={6}>
                  <Form.Item name={['settings', 'backup', 'enabled']} valuePropName="checked" label={t('enable_backup')} style={{ marginBottom: 0 }}>
                    <Switch />
                  </Form.Item>
                </Col>
                <Col span={18}>
                  <Form.Item label={t('backup_path')} style={{ marginBottom: 0 }}>
                    <Input.Group compact style={{ display: 'flex' }}>
                      <Form.Item name={['settings', 'backup', 'path']} noStyle>
                        <Input disabled={!backupEnabled} style={{ width: 'calc(100% - 32px)' }} />
                      </Form.Item>
                      <Button disabled={!backupEnabled} icon={<FolderOpenOutlined />} onClick={() => openBrowser('backup')} />
                    </Input.Group>
                  </Form.Item>
                </Col>
              </Row>
            </Card>

            <div style={{ position: 'sticky', bottom: 0, background: '#fff', padding: '15px', borderTop: '1px solid #eee', textAlign: 'right', zIndex: 10 }}>
              <Button type="primary" htmlType="submit" icon={<SaveOutlined />} loading={loading} size="large">
                {t('save_config')}
              </Button>
            </div>

          </Form>
        </div>
      </div>

      <FileBrowserModal 
        visible={browserVisible} 
        onCancel={() => setBrowserVisible(false)}
        onSelect={handleBrowserSelect}
        initialPath={getInitialBrowserPath()}
        connectionType={browserConnectionType}
        connectionConfig={browserConfig}
      />

      <Modal
        title={t('preview')}
        open={previewVisible}
        onCancel={() => setPreviewVisible(false)}
        footer={[<Button key="ok" onClick={() => setPreviewVisible(false)}>{t('cancel')}</Button>]}
      >
        <p>Files matching <b>{form.getFieldValue(['settings', 'file_format'])}</b> in source:</p>
        <List
          size="small"
          bordered
          loading={previewLoading}
          dataSource={previewFiles}
          renderItem={item => <List.Item>{item}</List.Item>}
          locale={{ emptyText: 'No files found or path invalid.' }}
          style={{ maxHeight: 300, overflowY: 'auto' }}
        />
      </Modal>
    </MainLayout>
  );
};

export default Configuration;