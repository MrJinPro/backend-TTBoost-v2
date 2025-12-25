import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { Header } from "@/components/Header";
import { Footer } from "@/components/Footer";
import { AuthForm } from "@/components/AuthForm";
import { getToken } from "@/lib/api";
import starLogo from "@/assets/star-logo.png";

const Auth = () => {
  const navigate = useNavigate();

  useEffect(() => {
    if (getToken()) {
      navigate('/profile');
    }
  }, [navigate]);

  const handleSuccess = () => {
    navigate('/profile');
  };

  return (
    <div className="min-h-screen">
      <Header />
      
      <main className="pt-32 pb-20 px-4">
        <div className="container mx-auto max-w-md">
          <div className="text-center mb-8">
            <img 
              src={starLogo} 
              alt="NovaBoost" 
              className="h-16 w-16 mx-auto mb-4 animate-float"
            />
          </div>
          
          <AuthForm onSuccess={handleSuccess} />
        </div>
      </main>

      <Footer />
    </div>
  );
};

export default Auth;
