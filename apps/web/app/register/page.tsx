import React, { Suspense } from 'react';
import AuthLayout from '../../components/auth/AuthLayout';
import RegisterForm from '../../components/auth/RegisterForm';

export const metadata = {
  title: 'Create Account | Migraflow Platform',
  description: 'Register a new account on Migraflow Data Migration Platform',
};

const AUTH_SPLINE_URL = 'https://my.spline.design/flow-vD4AAB4End71ev0QfMLT00qI/';

export default function RegisterPage() {
  return (
    <AuthLayout
      title="Create Your Account"
      subtitle="Join Migraflow to translate database schemas with AI and execute high-speed streaming ETL migrations."
      sceneUrl={AUTH_SPLINE_URL}
    >
      <Suspense fallback={<div className="text-zinc-500 text-xs py-4 text-center">Loading sign-up...</div>}>
        <RegisterForm />
      </Suspense>
    </AuthLayout>
  );
}
