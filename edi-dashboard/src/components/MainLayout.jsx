import React from 'react';
import { Layout, Menu, Button, Dropdown } from 'antd';
import { DashboardOutlined, SettingOutlined, ToolOutlined, LogoutOutlined, UserOutlined, GlobalOutlined } from '@ant-design/icons';
import { useNavigate, useLocation } from 'react-router-dom';
import { useLanguage } from '../contexts/LanguageContext';

const { Header, Sider, Content } = Layout;

const MainLayout = ({ children }) => {
  const navigate = useNavigate();
  const location = useLocation();
  const { t, setLang, lang } = useLanguage();
  
  const handleLogout = () => {
    localStorage.removeItem('edi_token');
    navigate('/login');
  };

  const items = [
    { key: '/dashboard', icon: <DashboardOutlined />, label: t('dashboard') },
    { key: '/profiles', icon: <SettingOutlined />, label: t('configuration') },
    { key: '/system', icon: <ToolOutlined />, label: t('system') },
  ];

  const langMenu = {
    items: [
      { key: 'en', label: 'English 🇺🇸', onClick: () => setLang('en') },
      { key: 'pt', label: 'Português 🇧🇷', onClick: () => setLang('pt') },
    ]
  };

  return (
    <Layout style={{ minHeight: '100vh', width: '100%' }}>
      <Header style={{ background: '#003366', padding: '0 20px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', height: '50px', boxShadow: '0 2px 5px rgba(0,0,0,0.2)', zIndex: 10 }}>
        <div style={{ display: 'flex', alignItems: 'center', color: 'white', fontSize: '16px', fontWeight: '600' }}>
          <span style={{ background: '#ff6400', color: 'white', padding: '0 6px', marginRight: '8px', borderRadius: '2px', fontSize: '12px', fontWeight: 'bold' }}>APMT</span>
          EDI CONTROL
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '15px' }}>
          <Dropdown menu={langMenu}>
            <Button type="text" style={{ color: 'white' }} icon={<GlobalOutlined />}>
              {lang === 'en' ? 'EN' : 'PT'}
            </Button>
          </Dropdown>
          <div style={{ color: 'rgba(255,255,255,0.85)', fontSize: '13px' }}>
            <UserOutlined style={{ marginRight: 5 }} /> admin
          </div>
          <Button type="text" icon={<LogoutOutlined />} onClick={handleLogout} style={{ color: '#fff', fontSize: '13px' }} size="small">
            {t('logout')}
          </Button>
        </div>
      </Header>

      <Layout>
        <Sider width={200} style={{ background: '#f5f7fa', borderRight: '1px solid #e8e8e8' }}>
          <Menu mode="inline" selectedKeys={[location.pathname]} style={{ height: '100%', borderRight: 0, background: '#f5f7fa' }} items={items} onClick={({ key }) => navigate(key)} />
        </Sider>
        
        <Layout style={{ padding: '0', background: '#fff' }}>
          <div style={{ background: '#f0f2f5', padding: '10px 24px', borderBottom: '1px solid #e8e8e8', color: '#555', fontWeight: '600', fontSize: '14px' }}>
             {items.find(i => i.key === location.pathname)?.label || 'Dashboard'}
          </div>
          <Content style={{ padding: '24px', margin: 0, minHeight: 280, overflow: 'auto' }}>
            {children}
          </Content>
        </Layout>
      </Layout>
    </Layout>
  );
};

export default MainLayout;