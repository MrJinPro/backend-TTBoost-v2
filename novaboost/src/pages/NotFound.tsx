import { Link, useLocation } from "react-router-dom";
import { useEffect } from "react";
import { Header } from "@/components/Header";
import { Footer } from "@/components/Footer";

const NotFound = () => {
  const location = useLocation();

  useEffect(() => {
    console.error("404 Error: User attempted to access non-existent route:", location.pathname);
  }, [location.pathname]);

  return (
    <div className="min-h-screen flex flex-col">
      <Header />
      <main className="flex-1 pt-32 pb-20 px-4">
        <div className="container mx-auto max-w-xl text-center">
          <h1 className="mb-3 text-5xl font-bold text-foreground">404</h1>
          <p className="mb-6 text-muted-foreground">Страница не найдена: {location.pathname}</p>
          <Link to="/" className="text-primary underline hover:text-primary/90">
            На главную
          </Link>
        </div>
      </main>
      <Footer />
    </div>
  );
};

export default NotFound;
