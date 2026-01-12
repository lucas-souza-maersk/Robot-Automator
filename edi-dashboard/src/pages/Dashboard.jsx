import React, { useState, useEffect } from 'react';
import { Table, Tag, Input, Button, Card, message, Select, Row, Col, Statistic, Switch } from 'antd';
import { ReloadOutlined, SendOutlined } from '@ant-design/icons';
import MainLayout from '../components/MainLayout';
import api from '../services/api';
import { useLanguage } from '../contexts/LanguageContext'; // Importe o contexto

const { Option } = Select;

const Dashboard = () => {
  const { t } = useLanguage(); // Use a tradução
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState([]);
  const [stats, setStats] = useState({ pending: 0, sent: 0, failed: 0, duplicate: 0 });
  const [profiles, setProfiles] = useState([]);
  const [selectedProfile, setSelectedProfile] = useState('');
  const [searchText, setSearchText] = useState('');
  const [selectedRowKeys, setSelectedRowKeys] = useState([]);
  const [autoRefresh, setAutoRefresh] = useState(true); // Estado do Auto Refresh

  useEffect(() => {
    fetchProfiles();
  }, []);

  // AUTO REFRESH LOGIC
  useEffect(() => {
    let interval;
    if (autoRefresh && selectedProfile) {
      interval = setInterval(() => {
        fetchQueueData(true); // Silent refresh
        fetchStats();
      }, 5000); // 5 segundos
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
      const profilesArray = Object.keys(profilesData).map(key => ({
        name: key,
        ...profilesData[key]
      }));
      setProfiles(profilesArray);
      if (profilesArray.length > 0 && !selectedProfile) {
        setSelectedProfile(profilesArray[0].name);
      }
    } catch (error) {
      console.error(error);
    }
  };

  const fetchQueueData = async (silent = false) => {
    if (!selectedProfile) return;
    if (!silent) setLoading(true);
    try {
      // Agora o backend lida com virgulas e busca inteligente
      const url = searchText 
        ? `/queue/${selectedProfile}?search=${encodeURIComponent(searchText)}`
        : `/queue/${selectedProfile}`;

      const res = await api.get(url);
      setData(res.data);
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
      message.success('Files marked for forced resend.');
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
        return <Tag color={color}>{status.toUpperCase()}</Tag>;
      }
    },
    { title: t('filename'), dataIndex: 'filename', width: 250, ellipsis: true },
    { title: t('unit'), dataIndex: 'units', width: 150 },
    { title: t('retries'), dataIndex: 'retries', width: 80, align: 'center' },
    { title: t('added_at'), dataIndex: 'added_at', width: 160 },
    { title: t('processed_at'), dataIndex: 'processed_at', width: 160 },
  ];

  return (
    <MainLayout>
      <Card styles={{ body: { padding: '15px' } }} style={{ marginBottom: 20 }}>
        <Row gutter={16} align="middle">
          <Col span={5}>
            <span style={{ marginRight: 10 }}>{t('profile')}:</span>
            <Select value={selectedProfile} style={{ width: 180 }} onChange={setSelectedProfile}>
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
            <Switch 
              checkedChildren="Auto" 
              unCheckedChildren="Manual" 
              checked={autoRefresh} 
              onChange={setAutoRefresh} 
            />
            <Button icon={<ReloadOutlined />} onClick={() => { fetchQueueData(); fetchStats(); }}>
              {t('refresh')}
            </Button>
            <Button type="primary" danger icon={<SendOutlined />} onClick={handleForceResend} disabled={selectedRowKeys.length === 0}>
              {t('force_resend')} ({selectedRowKeys.length})
            </Button>
          </Col>
        </Row>
      </Card>

      <Row gutter={16} style={{ marginBottom: 20 }}>
        <Col span={6}><Card><Statistic title={t('queue_pending')} value={stats.pending} valueStyle={{ color: '#1890ff' }} /></Card></Col>
        <Col span={6}><Card><Statistic title={t('sent_success')} value={stats.sent} valueStyle={{ color: '#3f8600' }} /></Card></Col>
        <Col span={6}><Card><Statistic title={t('failed')} value={stats.failed} valueStyle={{ color: '#cf1322' }} /></Card></Col>
        <Col span={6}><Card><Statistic title={t('duplicates')} value={stats.duplicate} valueStyle={{ color: '#faad14' }} /></Card></Col>
      </Row>

      <Table columns={columns} dataSource={data} rowKey="id" loading={loading} size="small" pagination={{ pageSize: 15 }} 
             rowSelection={{ selectedRowKeys, onChange: setSelectedRowKeys }} bordered scroll={{ y: 500 }} />
    </MainLayout>
  );
};

export default Dashboard;