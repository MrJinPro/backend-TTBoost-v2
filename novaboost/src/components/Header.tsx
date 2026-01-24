import { Link, useLocation } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { getToken, removeToken } from "@/lib/api";
import starLogo from "@/assets/star-logo.png";
import { useEffect, useState } from "react";
import { authApi } from "@/lib/api";
import { Play } from "lucide-react";
import { ANDROID_TEST_URL } from "@/lib/config";

interface HeaderProps {
  isLoggedIn?: boolean;
  onLogout?: () => void;
}

export const Header = ({ isLoggedIn, onLogout }: HeaderProps) => {
  const location = useLocation();
  const token = getToken();
  const loggedIn = isLoggedIn ?? !!token;
  const [isStaff, setIsStaff] = useState(false);

  useEffect(() => {
    let cancelled = false;
    if (!loggedIn) {
      setIsStaff(false);
      return;
    }

    (async () => {
      try {
        const me = await authApi.getMe();
        const role = (me?.role || "user").toLowerCase();
        if (!cancelled) setIsStaff(role !== "user");
      } catch {
        if (!cancelled) setIsStaff(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [loggedIn]);

  const handleLogout = () => {
    removeToken();
    onLogout?.();
    window.location.href = '/';
  };

  return (
    <header className="fixed top-0 left-0 right-0 z-50 glass-card border-b border-border/30">
      <div className="container mx-auto px-4 h-16 flex items-center justify-between">
        <Link to="/" className="flex items-center gap-3 group">
          <img 
            src={starLogo} 
            alt="NovaBoost" 
            className="h-10 w-10 object-contain transition-transform duration-300 group-hover:scale-110 group-hover:rotate-12"
          />
          <span className="text-xl font-bold text-gradient-gold">NovaBoost</span>
        </Link>

        <nav className="flex items-center gap-4">
          <Button asChild variant="outline" size="sm">
            <a
              href={ANDROID_TEST_URL}
              target="_blank"
              rel="noreferrer"
              aria-label="Google Play (тестирование)"
            >
              <Play className="h-4 w-4" />
              Google Play (тест)
            </a>
          </Button>
          {loggedIn ? (
            <>
              {isStaff && (
                <Link to="/admin/notifications">
                  <Button variant="ghost" size="sm">
                    Уведомления
                  </Button>
                </Link>
              )}
              <Link to="/profile">
                <Button variant="ghost" size="sm">
                  Профиль
                </Button>
              </Link>
              <Button variant="outline" size="sm" onClick={handleLogout}>
                Выйти
              </Button>
            </>
          ) : (
            <>
              {location.pathname !== '/auth' && (
                <Link to="/auth">
                  <Button variant="gold" size="sm">
                    Войти
                  </Button>
                </Link>
              )}
            </>
          )}
        </nav>
      </div>
    </header>
  );
};
