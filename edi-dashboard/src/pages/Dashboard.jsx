import React, { useState, useEffect } from 'react';
import { 
  Table, Tag, Input, Button, Card, message, Select, Row, Col, Statistic, Switch, 
  Descriptions, Tabs, Typography, Spin, Tooltip, DatePicker
} from 'antd';
import { 
  ReloadOutlined, SendOutlined, FileTextOutlined,
  LoginOutlined, LogoutOutlined, ContainerOutlined, InfoCircleOutlined,
  CheckCircleOutlined, EyeOutlined, SyncOutlined, CloseCircleOutlined, WarningOutlined
} from '@ant-design/icons';
import MainLayout from '../components/MainLayout';
import api from '../services/api';
import { useLanguage } from '../contexts/LanguageContext';
import dayjs from 'dayjs';
import utc from 'dayjs/plugin/utc'; // Importação necessária para lidar com UTC

// Ativa o plugin UTC (se não tiver instalado, o código abaixo usa um fallback nativo)
try { dayjs.extend(utc); } catch (e) {}

const { Option } = Select;
const { TabPane } = Tabs;
const { Paragraph } = Typography;
const { RangePicker } = DatePicker;

// --- FUNÇÃO DE CONVERSÃO DE DATA (SOLUÇÃO DO PROBLEMA 12h vs 9h) ---
const formatToLocal = (dateStr) => {
  if (!dateStr) return '-';
  try {
    // O SQLite retorna algo como "2026-01-29 12:00:00" que é UTC.
    // Adicionamos 'Z' para forçar o Javascript a entender que é UTC.
    // O dayjs/browser converte automaticamente para o fuso local (Brasil).
    return dayjs(dateStr + 'Z').format('DD/MM/YYYY HH:mm:ss');
  } catch (error) {
    return dateStr; // Se falhar, retorna original
  }
};

// --- FILE DETAIL COMPONENT ---
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
        <TabPane tab={`Parsed Data (${ediTransactions.length})`} key="1">
          <div style={{ maxHeight: 'calc(100vh - 250px)', overflowY: 'auto', paddingRight: '5px' }}>
            
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
                  <Descriptions bordered column={1} size="middle" layout="horizontal">
                    
                    <Descriptions.Item label="UNIT (Container)">
                        <b style={{ fontSize: '1.2em', color: '#1890ff' }}>{tx.container || 'N/A'}</b>
                    </Descriptions.Item>

                    <Descriptions.Item label="Function">{renderFunction(tx.function)}</Descriptions.Item>
                    
                    <Descriptions.Item label="Event Date">
                        {/* Data extraída do arquivo geralmente já é local, mantemos. Se não, fallback pro sistema */}
                        <b style={{ color: '#000' }}>{tx.date || 'N/A'}</b>
                    </Descriptions.Item>

                    <Descriptions.Item label="Status">
                      {tx.status === 'Full (Cheio)' ? <Tag color="red">FULL</Tag> : 
                       tx.status === 'Empty (Vazio)' ? <Tag color="green">EMPTY</Tag> : tx.status}
                    </Descriptions.Item>
                    
                    <Descriptions.Item label="ISO">{tx.iso_code}</Descriptions.Item>
                    <Descriptions.Item label="Booking">{tx.booking}</Descriptions.Item>
                    <Descriptions.Item label="Transport">{tx.transport}</Descriptions.Item>
                    
                    {(tx.vgm && tx.vgm !== 'N/A') && (
                      <Descriptions.Item label="VGM"><Tag color="gold">{tx.vgm}</Tag></Descriptions.Item>
                    )}
                    
                    {(tx.seals?.length > 0) && (
                      <Descriptions.Item label="Seals">
                        {tx.seals.map(s => <Tag key={s} color="purple">{s}</Tag>)}
                      </Descriptions.Item>
                    )}
                    
                     {(tx.remarks?.length > 0) && (
                      <Descriptions.Item label="Remarks">
                        <span style={{ color: '#666', fontStyle: 'italic' }}>{tx.remarks.join(', ')}</span>
                      </Descriptions.Item>
                    )}
                  </Descriptions>
                )}
              </Card>
            ))}

            {ediTransactions.length === 0 && <div style={{textAlign:'center'}}>No valid EDI transactions found.</div>}
          </div>
        </TabPane>

        <TabPane tab="Raw EDI Content" key="2">
          <Paragraph>
            <pre style={{ background: '#f5f5f5', padding: 15, borderRadius: 5, fontSize: '11px', whiteSpace: 'pre-wrap', border: '1px solid #e0e0e0', maxHeight: '600px', overflowY: 'auto' }}>
              {data.raw_content || 'No content found.'}
            </pre>
          </Paragraph>
        </TabPane>
        
        <TabPane tab="System Info" key="3">
             <Descriptions bordered column={1} size="small">
                {/* AQUI TAMBÉM APLICAMOS A CORREÇÃO DE DATA */}
                <Descriptions.Item label="System Added At">{formatToLocal(data.db_info?.added_at)}</Descriptions.Item>
                <Descriptions.Item label="Processed At">{formatToLocal(data.db_info?.processed_at)}</Descriptions.Item>
                <Descriptions.Item label="File Hash">{data.db_info?.hash}</Descriptions.Item>
                <Descriptions.Item label="File Path">{data.db_info?.file_path}</Descriptions.Item>
             </Descriptions>
        </TabPane>
      </Tabs>
    </Card>
  );
};

// --- MONITORING VIEW ---
const MonitoringView = ({ onOpenFile }) => {
  const { t } = useLanguage();
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState([]);
  const [stats, setStats] = useState({ pending: 0, sent: 0, failed: 0, duplicate: 0, monitored: 0 });
  const [profiles, setProfiles] = useState([]);
  const [selectedProfile, setSelectedProfile] = useState('');
  const [searchText, setSearchText] = useState('');
  const [dateRange, setDateRange] = useState(null);
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
  }, [autoRefresh, selectedProfile, searchText, dateRange]);

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
      let url = `/queue/${selectedProfile}`;
      const params = new URLSearchParams();
      
      if (searchText) params.append('search', searchText);
      
      if (dateRange && dateRange[0] && dateRange[1]) {
        params.append('date_start', dateRange[0].format('YYYY-MM-DD'));
        params.append('date_end', dateRange[1].format('YYYY-MM-DD'));
      }

      const queryString = params.toString();
      if (queryString) url += `?${queryString}`;

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
    { title: 'ID', dataIndex: 'id', width: 60, responsive: ['md'] },
    { 
      title: t('status'), 
      dataIndex: 'status', 
      width: 130,
      render: status => {
        let color = 'default';
        let icon = null;
        let text = status ? status.toUpperCase() : 'UNKNOWN';

        if (status === 'sent') { color = 'success'; icon = <CheckCircleOutlined />; }
        else if (status === 'failed') { color = 'error'; icon = <CloseCircleOutlined />; }
        else if (status === 'pending') { color = 'processing'; icon = <SyncOutlined spin />; }
        else if (status === 'duplicate') { color = 'warning'; icon = <WarningOutlined />; }
        else if (status === 'monitored') { color = 'cyan'; icon = <EyeOutlined />; text = 'CAPTURED'; }

        return <Tag color={color} icon={icon}>{text}</Tag>;
      }
    },
    { title: t('filename'), dataIndex: 'filename', ellipsis: true },
    { title: t('unit'), dataIndex: 'units', width: 150, responsive: ['sm'] },
    
    // COLUNA DE DATA DE EVENTO (CORRIGIDA)
    { 
        title: 'Event Date', 
        dataIndex: 'event_date', 
        width: 150, 
        responsive: ['lg'],
        render: (date, record) => {
             // Se tem data do evento REAL (que veio do arquivo), mostra ela (confiamos que o arquivo tá certo)
             if (date) return <Tag color="geekblue">{date}</Tag>;
             
             // Se não tem, usa o fallback (Data do Sistema) MAS CONVERTIDO PRA BRASIL
             // O "Z" força o JS a entender que a data original é UTC, e o format converte pro seu PC
             const localDate = formatToLocal(record.added_at);
             return <span style={{color: '#ccc'}}>{localDate}</span>;
        }
    },

    // COLUNA ADDED AT (CORRIGIDA - Convertendo UTC para Local)
    { 
        title: t('added_at'), 
        dataIndex: 'added_at', 
        width: 160, 
        responsive: ['xl'],
        render: (date) => formatToLocal(date)
    },
  ];

  return (
    <div>
      {/* HEADER DE CONTROLES */}
      <Card styles={{ body: { padding: '15px' } }} style={{ marginBottom: 16 }}>
        <Row gutter={[12, 12]} align="middle">
          {/* Profile Select */}
          <Col xs={24} sm={12} md={6} lg={4}>
            <div style={{ fontSize: '12px', color: '#888', marginBottom: 2 }}>{t('profile')}:</div>
            <Select value={selectedProfile} style={{ width: '100%' }} onChange={setSelectedProfile} loading={profiles.length === 0}>
              {profiles.map(p => <Option key={p.name} value={p.name}>{p.name}</Option>)}
            </Select>
          </Col>

          {/* Date Picker */}
          <Col xs={24} sm={12} md={8} lg={6}>
            <div style={{ fontSize: '12px', color: '#888', marginBottom: 2 }}>Filter by Date (Event or Added):</div>
            <RangePicker 
                style={{ width: '100%' }} 
                onChange={setDateRange} 
                value={dateRange}
                format="DD/MM/YYYY"
            />
          </Col>

          {/* Search Bar */}
          <Col xs={24} md={10} lg={8}>
            <div style={{ fontSize: '12px', color: '#888', marginBottom: 2 }}>Smart Search (Filename or Unit):</div>
            <Input.Search 
              placeholder="Ex: TCLU4622720..."
              onSearch={() => fetchQueueData()}
              onChange={e => setSearchText(e.target.value)}
              value={searchText}
              allowClear
              enterButton
            />
          </Col>

          {/* Action Buttons */}
          <Col xs={24} lg={6} style={{ display: 'flex', justifyContent: 'flex-end', alignItems: 'flex-end', gap: 8, flexWrap: 'wrap' }}>
             <Switch checkedChildren="Auto" unCheckedChildren="Manual" checked={autoRefresh} onChange={setAutoRefresh} />
             <Button icon={<ReloadOutlined />} onClick={() => { fetchQueueData(); fetchStats(); }} />
             <Tooltip title="Force Resend">
                <Button type="primary" danger icon={<SendOutlined />} onClick={handleForceResend} disabled={selectedRowKeys.length === 0}>
                   {selectedRowKeys.length > 0 ? `(${selectedRowKeys.length})` : ''}
                </Button>
            </Tooltip>
          </Col>
        </Row>
      </Card>

      {/* STATS CARDS */}
      <Row gutter={[8, 8]} style={{ marginBottom: 16 }}>
        <Col xs={12} sm={8} md={4}><Card size="small" bodyStyle={{padding: 10}}><Statistic title="Pending" value={stats.pending} valueStyle={{ color: '#1890ff', fontSize: '1rem' }} /></Card></Col>
        <Col xs={12} sm={8} md={5}><Card size="small" bodyStyle={{padding: 10}}><Statistic title="Sent" value={stats.sent} prefix={<CheckCircleOutlined />} valueStyle={{ color: '#3f8600', fontSize: '1rem' }} /></Card></Col>
        <Col xs={12} sm={8} md={5}><Card size="small" bodyStyle={{padding: 10}}><Statistic title="Captured" value={stats.monitored || 0} prefix={<EyeOutlined />} valueStyle={{ color: '#13c2c2', fontSize: '1rem' }} /></Card></Col>
        <Col xs={12} sm={8} md={5}><Card size="small" bodyStyle={{padding: 10}}><Statistic title="Dupe" value={stats.duplicate} valueStyle={{ color: '#faad14', fontSize: '1rem' }} /></Card></Col>
        <Col xs={12} sm={8} md={5}><Card size="small" bodyStyle={{padding: 10}}><Statistic title="Failed" value={stats.failed} valueStyle={{ color: '#cf1322', fontSize: '1rem' }} /></Card></Col>
      </Row>

      {/* TABLE */}
      <div style={{ background: '#fff', borderRadius: '8px', border: '1px solid #f0f0f0' }}>
        <Table 
            columns={columns} 
            dataSource={data} 
            rowKey="id" 
            loading={loading} 
            size="small" 
            pagination={{ pageSize: 20, showSizeChanger: false }} 
            rowSelection={{ selectedRowKeys, onChange: setSelectedRowKeys }} 
            bordered 
            scroll={{ x: 800, y: 'calc(100vh - 420px)' }}
            onRow={(record) => ({
            onClick: () => onOpenFile(record, selectedProfile),
            style: { cursor: 'pointer' }
            })}
        />
      </div>
    </div>
  );
};

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