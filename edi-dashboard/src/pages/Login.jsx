import React, { useState } from 'react';
import { Form, Input, Button, message } from 'antd';
import { UserOutlined, LockOutlined, CloudServerOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import api from '../services/api';
import './Login.scss';

const Login = () => {
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const onFinish = async (values) => {
    setLoading(true);
    const formData = new FormData();
    formData.append('username', values.username);
    formData.append('password', values.password);

    try {
      const response = await api.post('/token', formData);
      const { access_token } = response.data;
      localStorage.setItem('edi_token', access_token);
      message.success('Login successful');
      navigate('/dashboard'); 
    } catch (error) {
      message.error('Invalid username or password.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-container">
      <div className="login-card">
        
        <div className="login-header">
          {/* Icon representing server/robot */}
          <CloudServerOutlined style={{ fontSize: '48px', color: '#00509E' }} />
          <h1>APM Terminals <br/> EDI Control</h1>
          <p>Automation & Monitoring</p>
        </div>
        
        <Form
          name="login_form"
          initialValues={{ remember: true }}
          onFinish={onFinish}
          size="large"
          layout="vertical"
        >
          <Form.Item
            name="username"
            rules={[{ required: true, message: 'Enter your username.' }]}
          >
            <Input 
              prefix={<UserOutlined style={{ color: '#00509E', opacity: 0.7 }} />} 
              placeholder="Username" 
            />
          </Form.Item>

          <Form.Item
            name="password"
            rules={[{ required: true, message: 'Enter your password.' }]}
          >
            <Input.Password 
              prefix={<LockOutlined style={{ color: '#00509E', opacity: 0.7 }} />} 
              placeholder="Password" 
            />
          </Form.Item>

          <Form.Item>
            <Button type="primary" htmlType="submit" loading={loading} block className="login-btn">
              Sign in
            </Button>
          </Form.Item>
        </Form>
      </div>
    </div>
  );
};

export default Login;
