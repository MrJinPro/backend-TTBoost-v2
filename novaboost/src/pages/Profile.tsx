import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Header } from "@/components/Header";
import { Footer } from "@/components/Footer";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { authApi, getToken, UserProfile } from "@/lib/api";
import { toast } from "sonner";
import { Loader2, Key, User, Calendar, Shield } from "lucide-react";

const Profile = () => {
  const navigate = useNavigate();
  const [user, setUser] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [licenseKey, setLicenseKey] = useState('');
  const [activating, setActivating] = useState(false);

  useEffect(() => {
    const token = getToken();
    if (!token) {
      navigate('/auth');
      return;
    }

    const fetchUser = async () => {
      try {
        const userData = await authApi.getMe();
        setUser(userData);
      } catch {
        toast.error('Не удалось загрузить профиль');
        setUser(null);
      } finally {
        setLoading(false);
      }
    };

    fetchUser();
  }, [navigate]);

  const handleActivateLicense = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!licenseKey.trim()) {
      toast.error('Введите лицензионный ключ');
      return;
    }

    setActivating(true);

    try {
      await authApi.upgradeLicense(licenseKey);
      toast.success('Лицензия активирована!');
      // Refresh user data
      const userData = await authApi.getMe();
      setUser(userData);
      setLicenseKey('');
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Ошибка активации');
    } finally {
      setActivating(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  const formattedExpiry = user?.license_expires_at 
    ? new Date(user.license_expires_at).toLocaleDateString('ru-RU', {
        day: 'numeric',
        month: 'long',
        year: 'numeric',
      })
    : null;

  return (
    <div className="min-h-screen">
      <Header isLoggedIn={true} />
      
      <main className="pt-32 pb-20 px-4">
        <div className="container mx-auto max-w-2xl space-y-8">
          {/* User Info Card */}
          <Card className="animate-fade-in">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <User className="h-5 w-5 text-primary" />
                Профиль
              </CardTitle>
              <CardDescription>
                Информация о вашем аккаунте
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="p-4 rounded-xl bg-secondary/30 border border-border/50">
                  <p className="text-sm text-muted-foreground mb-1">Логин</p>
                  <p className="font-medium text-foreground">{user?.username}</p>
                </div>
                <div className="p-4 rounded-xl bg-secondary/30 border border-border/50">
                  <p className="text-sm text-muted-foreground mb-1">ID</p>
                  <p className="font-medium text-foreground font-mono text-sm">
                    {user?.id?.slice(0, 8)}...
                  </p>
                </div>
              </div>

              {user?.role && user.role.toLowerCase() !== 'user' && (
                <div className="pt-2">
                  <div className="flex flex-wrap gap-2">
                    <Button variant="outline" onClick={() => navigate('/admin')}>
                      Админка
                    </Button>
                    <Button variant="outline" onClick={() => navigate('/admin/notifications')}>
                      Админ: уведомления
                    </Button>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Current Plan Card */}
          <Card className="animate-fade-in-delay-1">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Shield className="h-5 w-5 text-primary" />
                Лицензия
              </CardTitle>
            </CardHeader>
            <CardContent>
              {user?.plan ? (
                <div className="space-y-4">
                  <div className="p-4 rounded-xl bg-primary/10 border border-primary/30">
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="font-semibold text-foreground text-lg">
                          {user.tariff_name || user.plan}
                        </p>
                        <div className="flex items-center gap-2 mt-1">
                          {user.allowed_platforms?.map((platform) => (
                            <span 
                              key={platform}
                              className="px-2 py-0.5 rounded-md bg-secondary text-muted-foreground text-xs"
                            >
                              {platform}
                            </span>
                          ))}
                        </div>
                      </div>
                      {formattedExpiry && (
                        <div className="text-right">
                          <div className="flex items-center gap-1 text-muted-foreground text-sm">
                            <Calendar className="h-4 w-4" />
                            <span>до {formattedExpiry}</span>
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              ) : (
                <div className="text-center py-6">
                  <p className="text-muted-foreground">
                    У вас нет активной лицензии.
                  </p>
                </div>
              )}
            </CardContent>
          </Card>

          {/* License Activation Card */}
          <Card className="animate-fade-in-delay-2">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Key className="h-5 w-5 text-primary" />
                Активация лицензии
              </CardTitle>
              <CardDescription>
                Введите лицензионный ключ для активации тарифа
              </CardDescription>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleActivateLicense} className="space-y-4">
                <Input
                  placeholder="TTB-XXXX-XXXX-XXXX"
                  value={licenseKey}
                  onChange={(e) => setLicenseKey(e.target.value.toUpperCase())}
                  disabled={activating}
                  className="font-mono"
                />
                <Button 
                  type="submit" 
                  variant="gold" 
                  className="w-full"
                  disabled={activating || !licenseKey.trim()}
                >
                  {activating ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin" />
                      Активация...
                    </>
                  ) : (
                    'Активировать'
                  )}
                </Button>
              </form>
            </CardContent>
          </Card>
        </div>
      </main>

      <Footer />
    </div>
  );
};

export default Profile;
