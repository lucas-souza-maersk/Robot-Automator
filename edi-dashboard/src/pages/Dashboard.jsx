import React, { useState, useEffect } from 'react';
import { 
  Table, Tag, Input, Button, Card, message, Select, Row, Col, Statistic, Switch, 
  Descriptions, Divider, Tabs, Typography, Spin 
} from 'antd';
import { 
  ReloadOutlined, SendOutlined, FileTextOutlined,
  LoginOutlined, LogoutOutlined, ContainerOutlined, InfoCircleOutlined
} from '@ant-design/icons';
import MainLayout from '../components/MainLayout';
import api from '../services/api';
import { useLanguage } from '../contexts/LanguageContext';

const { Option } = Select;
const { TabPane } = Tabs;
const { Paragraph } = Typography;

// ============================================================================
// COMPONENTE 1: CONTEÚDO DA ABA DE DETALHES (LISTA DE CARDS)
// ============================================================================
const FileDetailContent = ({ profileName, fileId }) => {
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState(null);

  useEffect(() => {
    const fetchDetails = async () => {
      try {
        const res = await api.get(`/queue/${profileName}/file/${fileId}`);
        setData(res.data);
      } catch (error) {
        message.error('Failed to load file details');
      } finally {
        setLoading(false);
      }
    };
    fetchDetails();
  }, [profileName, fileId]);

  // Função para ícones coloridos de Gate In/Out
  const renderFunction = (funcName) => {
    if (!funcName) return '-';
    const lower = funcName.toLowerCase();
    
    if (lower.includes('gate in')) {
      return <span style={{ color: '#1890ff', display: 'flex', alignItems: 'center', gap: '5px' }}><LoginOutlined /> <b>{funcName}</b></span>;
    }
    if (lower.includes('gate out')) {
      return <span style={{ color: '#1890ff', display: 'flex', alignItems: 'center', gap: '5px' }}><LogoutOutlined /> <b>{funcName}</b></span>;
    }
    return <b>{funcName}</b>;
  };

  if (loading) return <div style={{ textAlign: 'center', padding: 50 }}><Spin size="large" tip="Loading data..." /></div>;
  if (!data) return <div style={{ textAlign: 'center', padding: 50 }}>Data not found.</div>;

  const ediTransactions = Array.isArray(data.edi_info) ? data.edi_info : [data.edi_info];

  return (
    <Card bordered={false} style={{ minHeight: '100%' }}>
      <Tabs defaultActiveKey="1" type="card">
        {/* ABA 1: Parsed Data */}
        <TabPane tab={`Parsed Data (${ediTransactions.length})`} key="1">
          <div style={{ maxHeight: '650px', overflowY: 'auto', paddingRight: '5px' }}>
            
            {ediTransactions.map((tx, index) => (
              <Card 
                key={index} 
                size="small" 
                title={<span><ContainerOutlined /> {tx.container || `Transaction #${index+1}`}</span>} 
                extra={<Tag color="blue">{tx.type}</Tag>}
                style={{ marginBottom: 15, border: '1px solid #d9d9d9', background: '#fafafa' }}
                headStyle={{ background: '#f0f2f5' }}
              >
                {tx.error ? (
                  <div style={{ color: 'red', padding: 10 }}>
                    <InfoCircleOutlined /> <b>Error Parsing:</b> {tx.error}
                  </div>
                ) : (
                  <Descriptions bordered column={1} size="small">
                    <Descriptions.Item label="Function">{renderFunction(tx.function)}</Descriptions.Item>
                    <Descriptions.Item label="Status">
                      {tx.status === 'Full (Cheio)' ? <Tag color="red">FULL</Tag> : 
                       tx.status === 'Empty (Vazio)' ? <Tag color="green">EMPTY</Tag> : tx.status}
                    </Descriptions.Item>
                    <Descriptions.Item label="Date">{tx.date}</Descriptions.Item>
                    <Descriptions.Item label="ISO">{tx.iso_code}</Descriptions.Item>
                    <Descriptions.Item label="Booking">{tx.booking}</Descriptions.Item>
                    <Descriptions.Item label="Transport">{tx.transport}</Descriptions.Item>
                    
                    {(tx.seals?.length > 0) && (
                      <Descriptions.Item label="Seals">
                        {tx.seals.map(s => <Tag key={s} color="purple">{s}</Tag>)}
                      </Descriptions.Item>
                    )}
                    {(tx.genset && tx.genset !== 'N/A') && (
                      <Descriptions.Item label="Genset">{tx.genset}</Descriptions.Item>
                    )}
                     {(tx.remarks?.length > 0) && (
                      <Descriptions.Item label="Remarks">{tx.remarks.join(', ')}</Descriptions.Item>
                    )}
                  </Descriptions>
                )}
              </Card>
            ))}

            {ediTransactions.length === 0 && <div style={{textAlign:'center'}}>No valid EDI transactions found.</div>}
          </div>
        </TabPane>

        {/* ABA 2: Raw Content */}
        <TabPane tab="Raw EDI Content" key="2">
          <Paragraph>
            <pre style={{ background: '#f5f5f5', padding: 15, borderRadius: 5, fontSize: '11px', whiteSpace: 'pre-wrap', border: '1px solid #e0e0e0', maxHeight: '600px', overflowY: 'auto' }}>
              {data.raw_content || 'No content found.'}
            </pre>
          </Paragraph>
        </TabPane>
      </Tabs>
    </Card>
  );
};

// ============================================================================
// COMPONENTE 2: MONITORAMENTO (Tabela)
// ============================================================================
const MonitoringView = ({ onOpenFile }) => {
  const { t } = useLanguage();
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState([]);
  const [stats, setStats] = useState({ pending: 0, sent: 0, failed: 0, duplicate: 0 });
  const [profiles, setProfiles] = useState([]);
  const [selectedProfile, setSelectedProfile] = useState('');
  const [searchText, setSearchText] = useState('');
  const [selectedRowKeys, setSelectedRowKeys] = useState([]);
  const [autoRefresh, setAutoRefresh] = useState(true);

  useEffect(() => {
    fetchProfiles();
  }, []);

  useEffect(() => {
    let interval;
    if (autoRefresh && selectedProfile) {
      interval = setInterval(() => {
        fetchQueueData(true);
        fetchStats();
      }, 5000);
    }
    return () => clearInterval(interval);
  }, [autoRefresh, selectedProfile, searchText]);

  useEffect(() => {
    if (selectedProfile) {
      fetchQueueData();
      fetchStats();
    }
  }, [selectedProfile]);

  const fetchProfiles = async () => {
    try {
      const res = await api.get('/profiles');
      const profilesData = res.data || {};
      const profilesArray = Object.keys(profilesData).map(key => ({ name: key, ...profilesData[key] }));
      setProfiles(profilesArray);
      if (profilesArray.length > 0 && !selectedProfile) setSelectedProfile(profilesArray[0].name);
    } catch (error) {
      message.error('Error loading profiles.');
    }
  };

  const fetchQueueData = async (silent = false) => {
    if (!selectedProfile) return;
    if (!silent) setLoading(true);
    try {
      const url = searchText 
        ? `/queue/${selectedProfile}?search=${encodeURIComponent(searchText)}`
        : `/queue/${selectedProfile}`;
      const res = await api.get(url);
      setData(Array.isArray(res.data) ? res.data : []);
    } catch (error) {
      if (!silent) message.error('Error loading queue.');
    } finally {
      if (!silent) setLoading(false);
    }
  };

  const fetchStats = async () => {
    if (!selectedProfile) return;
    try {
      const res = await api.get(`/stats/${selectedProfile}`);
      setStats(res.data);
    } catch (error) { console.error(error); }
  };

  const handleForceResend = async () => {
    if (selectedRowKeys.length === 0) return message.warning('Select files.');
    try {
      await api.post('/resend', { profile_name: selectedProfile, item_ids: selectedRowKeys });
      message.success('Files queued for resend.');
      fetchQueueData();
      setSelectedRowKeys([]);
    } catch (error) {
      message.error('Error requesting resend.');
    }
  };

  const columns = [
    { title: 'ID', dataIndex: 'id', width: 60 },
    { 
      title: t('status'), 
      dataIndex: 'status', 
      width: 100,
      render: status => {
        let color = status === 'sent' ? 'success' : status === 'failed' ? 'error' : 'default';
        if (status === 'pending') color = 'processing';
        if (status === 'duplicate') color = 'warning';
        return <Tag color={color}>{status ? status.toUpperCase() : 'UNKNOWN'}</Tag>;
      }
    },
    { title: t('filename'), dataIndex: 'filename', width: 250, ellipsis: true },
    { title: t('unit'), dataIndex: 'units', width: 150 },
    { title: t('retries'), dataIndex: 'retries', width: 80, align: 'center' },
    { title: t('added_at'), dataIndex: 'added_at', width: 160 },
    { title: t('processed_at'), dataIndex: 'processed_at', width: 160 },
  ];

  return (
    <div>
      <Card styles={{ body: { padding: '15px' } }} style={{ marginBottom: 20 }}>
        <Row gutter={16} align="middle">
          <Col span={5}>
            <span style={{ marginRight: 10 }}>{t('profile')}:</span>
            <Select value={selectedProfile} style={{ width: 180 }} onChange={setSelectedProfile} loading={profiles.length === 0}>
              {profiles.map(p => <Option key={p.name} value={p.name}>{p.name}</Option>)}
            </Select>
          </Col>
          <Col span={7}>
            <Input.Search 
              placeholder={t('search_placeholder')}
              onSearch={() => fetchQueueData()}
              onChange={e => setSearchText(e.target.value)}
              value={searchText}
              allowClear
            />
          </Col>
          <Col span={12} style={{ textAlign: 'right', display: 'flex', justifyContent: 'flex-end', alignItems: 'center', gap: 10 }}>
            <Switch checkedChildren="Auto" unCheckedChildren="Manual" checked={autoRefresh} onChange={setAutoRefresh} />
            <Button icon={<ReloadOutlined />} onClick={() => { fetchQueueData(); fetchStats(); }}>{t('refresh')}</Button>
            <Button type="primary" danger icon={<SendOutlined />} onClick={handleForceResend} disabled={selectedRowKeys.length === 0}>
              {t('force_resend')} ({selectedRowKeys.length})
            </Button>
          </Col>
        </Row>
      </Card>

      <Row gutter={16} style={{ marginBottom: 20 }}>
        <Col span={6}><Card><Statistic title={t('queue_pending')} value={stats.pending} styles={{ content: { color: '#1890ff' } }} /></Card></Col>
        <Col span={6}><Card><Statistic title={t('sent_success')} value={stats.sent} styles={{ content: { color: '#3f8600' } }} /></Card></Col>
        <Col span={6}><Card><Statistic title={t('failed')} value={stats.failed} styles={{ content: { color: '#cf1322' } }} /></Card></Col>
        <Col span={6}><Card><Statistic title={t('duplicates')} value={stats.duplicate} styles={{ content: { color: '#faad14' } }} /></Card></Col>
      </Row>

      <Table 
        columns={columns} 
        dataSource={data} 
        rowKey="id" 
        loading={loading} 
        size="small" 
        pagination={{ pageSize: 15 }} 
        rowSelection={{ selectedRowKeys, onChange: setSelectedRowKeys }} 
        bordered 
        scroll={{ y: 500 }}
        onRow={(record) => ({
          onClick: () => onOpenFile(record, selectedProfile),
          style: { cursor: 'pointer' }
        })}
      />
    </div>
  );
};

// ============================================================================
// COMPONENTE PRINCIPAL: DASHBOARD
// ============================================================================
const Dashboard = () => {
  const { t } = useLanguage();
  const [activeKey, setActiveKey] = useState('monitoring');
  
  const [items, setItems] = useState([
    { 
      key: 'monitoring', 
      label: <span><FileTextOutlined /> {t('dashboard')}</span>, 
      closable: false, 
    }
  ]);

  const addTab = (fileRecord, profileName) => {
    const newKey = `file-${fileRecord.id}`;
    
    if (items.find(i => i.key === newKey)) {
      setActiveKey(newKey);
      return;
    }

    const newTab = {
      key: newKey,
      label: fileRecord.filename || `File ${fileRecord.id}`,
      closable: true,
      children: <FileDetailContent profileName={profileName} fileId={fileRecord.id} />
    };

    setItems([...items, newTab]);
    setActiveKey(newKey);
  };

  const removeTab = (targetKey) => {
    const targetIndex = items.findIndex((item) => item.key === targetKey);
    const newItems = items.filter((item) => item.key !== targetKey);
    
    if (newItems.length && targetKey === activeKey) {
      const { key } = newItems[targetIndex === newItems.length ? targetIndex - 1 : targetIndex];
      setActiveKey(key);
    }
    setItems(newItems);
  };

  const onEdit = (targetKey, action) => {
    if (action === 'remove') {
      removeTab(targetKey);
    }
  };

  return (
    <MainLayout>
      <Tabs
        type="editable-card"
        hideAdd
        onChange={setActiveKey}
        activeKey={activeKey}
        onEdit={onEdit}
        items={items.map(item => {
          if (item.key === 'monitoring') {
            return { ...item, children: <MonitoringView onOpenFile={addTab} /> };
          }
          return item;
        })}
      />
    </MainLayout>
  );
};

export default Dashboard;