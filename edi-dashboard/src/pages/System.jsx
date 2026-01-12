import React, { useState, useEffect } from 'react';
import { Card, Tabs, Table, Button, Modal, Form, Input, Select, message, Popconfirm, Tag } from 'antd';
import { UserOutlined, BookOutlined, DeleteOutlined, PlusOutlined } from '@ant-design/icons';
import MainLayout from '../components/MainLayout';
import api from '../services/api';
import { useLanguage } from '../contexts/LanguageContext';

const { TabPane } = Tabs;
const { Option } = Select;

const System = () => {
  const { t } = useLanguage();
  const [users, setUsers] = useState([]);
  const [isModalVisible, setIsModalVisible] = useState(false);
  const [form] = Form.useForm();

  useEffect(() => {
    fetchUsers();
  }, []);

  const fetchUsers = async () => {
    try {
      const res = await api.get('/users');
      setUsers(res.data);
    } catch (error) {
      // Ignora erro se não for admin
    }
  };

  const handleCreateUser = async (values) => {
    try {
      await api.post('/users', values);
      message.success('User created!');
      setIsModalVisible(false);
      form.resetFields();
      fetchUsers();
    } catch (error) {
      message.error('Failed to create user. Username might exist.');
    }
  };

  const handleDeleteUser = async (username) => {
    try {
      await api.delete(`/users/${username}`);
      message.success('User deleted');
      fetchUsers();
    } catch (error) {
      message.error('Failed to delete user');
    }
  };

  const userColumns = [
    { title: t('username'), dataIndex: 'username', key: 'username' },
    { title: t('full_name'), dataIndex: 'full_name', key: 'full_name' },
    { 
      title: t('role'), 
      dataIndex: 'role', 
      key: 'role',
      render: role => <Tag color={role === 'admin' ? 'red' : 'blue'}>{role.toUpperCase()}</Tag>
    },
    {
      title: t('actions'),
      key: 'action',
      render: (_, record) => (
        record.username !== 'admin' && (
          <Popconfirm title={t('confirm_delete')} onConfirm={() => handleDeleteUser(record.username)}>
            <Button danger icon={<DeleteOutlined />} size="small">{t('delete')}</Button>
          </Popconfirm>
        )
      )
    }
  ];

  return (
    <MainLayout>
      <Tabs defaultActiveKey="1">
        
        {/* ABA 1: USUÁRIOS (AGORA EM PRIMEIRO) */}
        <TabPane tab={<span><UserOutlined /> {t('users')}</span>} key="1">
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setIsModalVisible(true)} style={{ marginBottom: 16 }}>
            {t('add_user')}
          </Button>
          <Table dataSource={users} columns={userColumns} rowKey="username" />
        </TabPane>

        {/* ABA 2: DOCUMENTAÇÃO (AGORA EM SEGUNDO E TRADUZIDA) */}
        <TabPane tab={<span><BookOutlined /> {t('documentation')}</span>} key="2">
          <Card title={t('doc_intro')}>
            <h3>{t('doc_mon_title')}</h3>
            <p>{t('doc_mon_desc')}</p>
            <ul>
              <li>{t('doc_mon_b1')}</li>
              <li>{t('doc_mon_b2')}</li>
            </ul>
            
            <h3>{t('doc_conf_title')}</h3>
            <p>{t('doc_conf_desc')}</p>
            <ul>
              <li>{t('doc_conf_b1')}</li>
              <li>{t('doc_conf_b2')}</li>
            </ul>

            <h3>{t('doc_user_title')}</h3>
            <p>{t('doc_user_desc')}</p>
          </Card>
        </TabPane>

      </Tabs>

      <Modal title={t('add_user')} open={isModalVisible} onCancel={() => setIsModalVisible(false)} footer={null}>
        <Form form={form} layout="vertical" onFinish={handleCreateUser}>
          <Form.Item name="username" label={t('username')} rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="full_name" label={t('full_name')}>
            <Input />
          </Form.Item>
          <Form.Item name="password" label={t('password')} rules={[{ required: true }]}>
            <Input.Password />
          </Form.Item>
          <Form.Item name="role" label={t('role')} initialValue="viewer">
            <Select>
              <Option value="viewer">Viewer (Read Only)</Option>
              <Option value="admin">Admin (Full Access)</Option>
            </Select>
          </Form.Item>
          <Button type="primary" htmlType="submit" block>{t('save')}</Button>
        </Form>
      </Modal>
    </MainLayout>
  );
};

export default System;