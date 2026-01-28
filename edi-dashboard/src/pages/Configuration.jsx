import React, { useState, useEffect } from 'react';
import { 
  Card, Form, Input, Button, Switch, Select, 
  message, Popconfirm, Row, Col, Divider, Modal, List, InputNumber, Radio, Tooltip
} from 'antd';
import { 
  SaveOutlined, PlusOutlined, DeleteOutlined, EditOutlined,
  FolderOpenOutlined, RobotOutlined, EyeOutlined,
  CloudServerOutlined, HddOutlined, DatabaseOutlined, FileTextOutlined,
  SendOutlined, InfoCircleOutlined
} from '@ant-design/icons';
import MainLayout from '../components/MainLayout';
import FileBrowserModal from '../components/FileBrowserModal';
import api from '../services/api';
import { useLanguage } from '../contexts/LanguageContext';

const { Option } = Select;

const Configuration = () => {
  const { t } = useLanguage();
  const [profiles, setProfiles] = useState({});
  const [activeProfile, setActiveProfile] = useState(null);
  const [loading, setLoading] = useState(false);
  
  const [renameModalVisible, setRenameModalVisible] = useState(false);
  const [newProfileName, setNewProfileName] = useState('');

  const [browserVisible, setBrowserVisible] = useState(false);
  const [browserField, setBrowserField] = useState(null);
  const [browserConnectionType, setBrowserConnectionType] = useState('local');
  const [browserConfig, setBrowserConfig] = useState({});
  
  const [previewVisible, setPreviewVisible] = useState(false);
  const [previewFiles, setPreviewFiles] = useState([]);
  const [previewLoading, setPreviewLoading] = useState(false);

  const [form] = Form.useForm();
  
  const sourceType = Form.useWatch(['source', 'type'], form);
  const destType = Form.useWatch(['destination', 'type'], form);
  const backupEnabled = Form.useWatch(['settings', 'backup', 'enabled'], form);
  const mode = Form.useWatch('mode', form);
  const autoResendEnabled = Form.useWatch(['auto_resend', 'enabled'], form);
  const fileAgeUnit = Form.useWatch(['settings', 'file_age', 'unit'], form);

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
    
    const profileData = { ...data[key] };
    if (!profileData.mode) profileData.mode = 'sender';
    if (!profileData.auto_resend) profileData.auto_resend = { enabled: false, interval_minutes: 60 };
    if (!profileData.settings.file_age) profileData.settings.file_age = { value: 0, unit: 'No Limit' };

    form.setFieldsValue(profileData);
  };

  const handleSave = async (values) => {
    setLoading(true);
    try {
      const updatedProfile = { 
        ...profiles[activeProfile], 
        ...values,
        settings: { ...profiles[activeProfile].settings, ...values.settings }
      };
      
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

  const openRenameModal = () => {
    setNewProfileName(activeProfile);
    setRenameModalVisible(true);
  };

  const handleRename = async () => {
    const trimmedName = newProfileName.trim();
    if (!trimmedName) return message.warning('Profile name cannot be empty');
    if (trimmedName === activeProfile) return setRenameModalVisible(false);
    if (profiles[trimmedName]) return message.error('A profile with this name already exists');

    setLoading(true);
    try {
      const updatedProfiles = { ...profiles };
      
      updatedProfiles[trimmedName] = { 
        ...updatedProfiles[activeProfile], 
        name: trimmedName 
      };
      
      delete updatedProfiles[activeProfile];

      await api.post('/profiles', { profiles: updatedProfiles });
      
      setProfiles(updatedProfiles);
      setActiveProfile(trimmedName); 
      setRenameModalVisible(false);
      message.success(`Renamed to ${trimmedName}`);
    } catch (error) {
      message.error('Failed to rename profile');
    } finally {
      setLoading(false);
    }
  };

  const createNewProfile = () => {
    const name = `Profile_${Object.keys(profiles).length + 1}`;
    const newProfile = {
      name: name,
      enabled: false,
      mode: 'sender',
      action: 'copy',
      source: { type: 'local', path: '' },
      destination: { type: 'local', path: '' },
      auto_resend: { enabled: false, interval_minutes: 60 },
      settings: {
        file_format: '*.edi',
        scan_interval: { value: 5, unit: 's' },
        file_age: { value: 0, unit: 'No Limit' },
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

  const openBrowser = (fieldIdentifier, type = 'local', sectionPrefix = null) => {
    setBrowserField(fieldIdentifier);
    setBrowserConnectionType(type);
    if (type === 'SFTP' && sectionPrefix) {
        const config = form.getFieldValue(sectionPrefix); 
        if (!config || !config.host || !config.username) return message.warning('Please fill Host and Username first.');
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
    return '';
  };

  const handlePreview = async () => {
    if (form.getFieldValue(['source', 'type']) !== 'local') return message.info('Preview only available for Local/Network paths.');
    const path = form.getFieldValue(['source', 'path']);
    const format = form.getFieldValue(['settings', 'file_format']);
    if (!path) return message.warning('Source path is empty');
    setPreviewLoading(true);
    setPreviewVisible(true);
    try {
      const res = await api.post('/system/preview', { path, pattern: format || '*.*' });
      setPreviewFiles(res.data.files);
    } catch (error) {
      setPreviewFiles([]);
    } finally {
      setPreviewLoading(false);
    }
  };

  const renderLocationFields = (prefix, type) => {
    const isSFTP = type === 'SFTP';
    if (isSFTP) {
      return (
        <>
          <Row gutter={8}>
            <Col span={16}><Form.Item name={[prefix, 'host']} label={t('host_ip')} rules={[{required:true}]}><Input prefix={<CloudServerOutlined />} /></Form.Item></Col>
            <Col span={8}><Form.Item name={[prefix, 'port']} label={t('port')}><InputNumber style={{width:'100%'}} defaultValue={22} /></Form.Item></Col>
          </Row>
          <Row gutter={8}>
            <Col span={12}><Form.Item name={[prefix, 'username']} label={t('username')} rules={[{required:true}]}><Input /></Form.Item></Col>
            <Col span={12}><Form.Item name={[prefix, 'password']} label={t('password')}><Input.Password /></Form.Item></Col>
          </Row>
          <Form.Item label={t('remote_path')}>
            <Input.Group compact style={{display:'flex'}}>
                <Form.Item name={[prefix, 'remote_path']} noStyle rules={[{required:true}]}><Input style={{width:'calc(100% - 32px)'}}/></Form.Item>
                <Button icon={<FolderOpenOutlined />} onClick={()=>openBrowser(`${prefix}_remote`,'SFTP',prefix)} />
            </Input.Group>
          </Form.Item>
        </>
      );
    }
    return (
      <Form.Item label={t('local_path')}>
        <Input.Group compact style={{display:'flex'}}>
          <Form.Item name={[prefix, 'path']} noStyle><Input style={{width:'calc(100% - 32px)'}} prefix={<HddOutlined />} /></Form.Item>
          <Button icon={<FolderOpenOutlined />} onClick={()=>openBrowser(prefix,'local')} />
        </Input.Group>
      </Form.Item>
    );
  };

  if (!activeProfile) return <MainLayout><div style={{textAlign:'center', marginTop:50}}><Button type="primary" icon={<PlusOutlined />} onClick={createNewProfile}>{t('create_profile')}</Button></div></MainLayout>;

  return (
    <MainLayout>
      <div style={{ display: 'flex', gap: 20, height: '100%' }}>
        <Card title={t('profiles_list')} style={{ width: 260, height: 'fit-content' }} extra={<Button type="dashed" size="small" icon={<PlusOutlined />} onClick={createNewProfile}>{t('new_profile')}</Button>}>
          <List size="small" dataSource={Object.keys(profiles)} renderItem={item => (
            <List.Item onClick={() => changeActiveProfile(item)} style={{ cursor: 'pointer', background: activeProfile === item ? '#e6f7ff' : 'transparent', borderLeft: activeProfile === item ? '3px solid #1890ff' : '3px solid transparent', paddingLeft: 10 }}>
              <span style={{ fontWeight: activeProfile === item ? 600 : 400 }}><RobotOutlined style={{ marginRight: 8 }} /> {item}</span>
            </List.Item>
          )} />
        </Card>

        <div style={{ flex: 1, overflowY: 'auto' }}>
          <Form form={form} layout="vertical" onFinish={handleSave}>
            <Card style={{ marginBottom: 20 }}>
              <Row justify="space-between" align="middle">
                <Col><h2 style={{ margin: 0 }}>{t('editing')}: {activeProfile}</h2></Col>
                <Col>
                  <Form.Item name="enabled" valuePropName="checked" noStyle><Switch checkedChildren={t('active_status')} unCheckedChildren={t('paused_status')} /></Form.Item>
                  
                  {/* BOTÃO RENOMEAR AQUI */}
                  <Tooltip title="Rename Profile">
                    <Button type="text" icon={<EditOutlined />} onClick={openRenameModal} style={{ marginLeft: 10 }} />
                  </Tooltip>

                  <Popconfirm title={t('confirm_delete')} onConfirm={deleteProfile}>
                    <Button danger type="text" icon={<DeleteOutlined />} style={{ marginLeft: 5 }}>{t('delete')}</Button>
                  </Popconfirm>
                </Col>
              </Row>
            </Card>

            <Card title={<span><InfoCircleOutlined /> Operation Mode</span>} style={{ marginBottom: 20 }} size="small">
              <Form.Item name="mode" initialValue="sender" style={{ marginBottom: 10 }}>
                <Radio.Group buttonStyle="solid" style={{ width: '100%' }}>
                  <Radio.Button value="sender" style={{ width: '50%', textAlign: 'center' }}><SendOutlined /> <b>Sender Mode</b> (Move & Send)</Radio.Button>
                  <Radio.Button value="visualizer" style={{ width: '50%', textAlign: 'center' }}><EyeOutlined /> <b>Visualizer Mode</b> (Monitor Only)</Radio.Button>
                </Radio.Group>
              </Form.Item>
              <div style={{ background: '#f5f5f5', padding: 10, borderRadius: 4, fontSize: '13px', color: '#666' }}>
                {mode === 'sender' ? "Move, Copy and Resend Archives" : "Monitor Source Location Only (can Resend Archives)"}<br />
              </div>
            </Card>

            <Row gutter={20}>
              <Col span={12}>
                <Card title={t('source_config')} type="inner" style={{ marginBottom: 20 }}>
                  <Form.Item name={['source', 'type']} label={t('source_type')}><Select><Option value="local">Local</Option><Option value="SFTP">SFTP</Option></Select></Form.Item>
                  {renderLocationFields('source', sourceType)}
                  
                  <Divider dashed style={{ margin: '10px 0' }} orientation="left">Filters & Pattern</Divider>
                  <Row gutter={10}>
                    <Col span={14}>
                      <Form.Item label="Process Newer Than" style={{ marginBottom: 0 }}>
                        <Input.Group compact>
                          <Form.Item name={['settings', 'file_age', 'value']} noStyle><InputNumber style={{ width: '40%' }} min={0} disabled={fileAgeUnit === 'No Limit'} /></Form.Item>
                          <Form.Item name={['settings', 'file_age', 'unit']} noStyle>
                            <Select style={{ width: '60%' }}>
                              <Option value="Days">Days</Option><Option value="Months">Months</Option><Option value="No Limit">No Limit</Option>
                            </Select>
                          </Form.Item>
                        </Input.Group>
                      </Form.Item>
                    </Col>
                    <Col span={10}>
                      <Form.Item label="Pattern" style={{ marginBottom: 0 }}>
                        <div style={{ display: 'flex', gap: 8 }}>
                          <Form.Item name={['settings', 'file_format']} noStyle><Input placeholder="*.edi" style={{ flex: 1 }} /></Form.Item>
                          <Tooltip title="Preview matches"><Button icon={<EyeOutlined />} onClick={handlePreview} /></Tooltip>
                        </div>
                      </Form.Item>
                    </Col>
                  </Row>
                </Card>
              </Col>
              <Col span={12}>
                <Card title={t('dest_config')} type="inner" style={{ marginBottom: 20 }}>
                  <Form.Item name={['destination', 'type']} label={t('dest_type')}><Select><Option value="local">Local</Option><Option value="SFTP">SFTP</Option></Select></Form.Item>
                  {renderLocationFields('destination', destType)}
                  {mode === 'sender' && (
                    <Form.Item name="action" label={t('post_action')}>
                      <Select><Option value="copy">{t('copy_action')}</Option><Option value="move">{t('move_action')}</Option></Select>
                    </Form.Item>
                  )}
                </Card>
              </Col>
            </Row>

            <Card title="Safety & Automation" style={{ marginBottom: 20 }}>
              <Row gutter={20} align="middle" style={{ marginBottom: 10 }}>
                <Col span={6}><Form.Item name={['settings', 'backup', 'enabled']} valuePropName="checked" label={t('enable_backup')} style={{ marginBottom: 0 }}><Switch /></Form.Item></Col>
                <Col span={18}>
                  <Form.Item label={t('backup_path')} style={{ marginBottom: 0 }}>
                    <Input.Group compact style={{display:'flex'}}>
                      <Form.Item name={['settings', 'backup', 'path']} noStyle><Input disabled={!backupEnabled} style={{width:'calc(100% - 32px)'}}/></Form.Item>
                      <Button disabled={!backupEnabled} icon={<FolderOpenOutlined />} onClick={()=>openBrowser('backup')} />
                    </Input.Group>
                  </Form.Item>
                </Col>
              </Row>
              <Divider dashed />
              <Row gutter={20} align="middle">
                <Col span={6}><Form.Item name={['auto_resend', 'enabled']} valuePropName="checked" label="Auto-Resend Loop" style={{ marginBottom: 0 }}><Switch /></Form.Item></Col>
                <Col span={18}>
                  {autoResendEnabled && (
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                      <span>Resend every</span>
                      <Form.Item name={['auto_resend', 'interval_minutes']} noStyle><InputNumber min={5} style={{ width: 80 }} /></Form.Item>
                      <span>minutes (Forever Loop)</span>
                    </div>
                  )}
                </Col>
              </Row>
            </Card>

            <Card title={t('system_settings')} style={{ marginBottom: 20 }}>
              <Row gutter={20}>
                <Col span={12}>
                  <Form.Item label={t('db_path')}>
                    <Input.Group compact style={{display:'flex'}}>
                      <Form.Item name={['settings', 'db_path']} noStyle><Input style={{width:'calc(100% - 32px)'}} prefix={<DatabaseOutlined />} /></Form.Item>
                      <Button icon={<FolderOpenOutlined />} onClick={()=>openBrowser('db')} />
                    </Input.Group>
                  </Form.Item>
                </Col>
                <Col span={12}>
                  <Form.Item label={t('log_path')}>
                    <Input.Group compact style={{display:'flex'}}>
                      <Form.Item name={['settings', 'log_path']} noStyle><Input style={{width:'calc(100% - 32px)'}} prefix={<FileTextOutlined />} /></Form.Item>
                      <Button icon={<FolderOpenOutlined />} onClick={()=>openBrowser('log')} />
                    </Input.Group>
                  </Form.Item>
                </Col>
              </Row>
            </Card>

            <div style={{ position: 'sticky', bottom: 0, background: '#fff', padding: '15px', borderTop: '1px solid #eee', textAlign: 'right', zIndex: 10 }}>
              <Button type="primary" htmlType="submit" icon={<SaveOutlined />} loading={loading} size="large">{t('save_config')}</Button>
            </div>
          </Form>
        </div>
      </div>

      <FileBrowserModal visible={browserVisible} onCancel={() => setBrowserVisible(false)} onSelect={handleBrowserSelect} initialPath={getInitialBrowserPath()} connectionType={browserConnectionType} connectionConfig={browserConfig} />

      <Modal title={t('preview')} open={previewVisible} onCancel={() => setPreviewVisible(false)} footer={[<Button key="ok" onClick={() => setPreviewVisible(false)}>{t('cancel')}</Button>]}>
        <p>Files matching <b>{form.getFieldValue(['settings', 'file_format'])}</b> in source:</p>
        <List size="small" bordered loading={previewLoading} dataSource={previewFiles} renderItem={item => <List.Item>{item}</List.Item>} locale={{ emptyText: 'No files found or path invalid.' }} style={{ maxHeight: 300, overflowY: 'auto' }} />
      </Modal>

      <Modal title="Rename Profile" open={renameModalVisible} onOk={handleRename} onCancel={() => setRenameModalVisible(false)} confirmLoading={loading}>
        <Input placeholder="New Profile Name" value={newProfileName} onChange={(e) => setNewProfileName(e.target.value)} />
      </Modal>

    </MainLayout>
  );
};

export default Configuration;