import React from 'react';
import AuthLayout from '../../components/auth/AuthLayout';
import LoginForm from '../../components/auth/LoginForm';

export const metadata = {
  title: 'Sign In | Migraflow Platform',
  description: 'Sign in to your Migraflow Data Migration Platform account',
};

const AUTH_SPLINE_URL = 'https://my.spline.design/flow-vD4AAB4End71ev0QfMLT00qI/';

export default function LoginPage() {
  return (
    <AuthLayout
      title="Welcome Back"
      subtitle="Sign in to Migraflow to manage database connection strings, schema plans, and active ETL streaming jobs."
      sceneUrl={AUTH_SPLINE_URL}
    >
      <LoginForm />
    </AuthLayout>
  );
}
