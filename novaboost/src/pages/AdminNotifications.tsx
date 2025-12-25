import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Header } from "@/components/Header";
import { Footer } from "@/components/Footer";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { toast } from "sonner";
import { authApi, getToken, adminApi, UserProfile } from "@/lib/api";
import { Loader2, BellRing, ShieldAlert } from "lucide-react";

const AdminNotifications = () => {
  const navigate = useNavigate();
  const [me, setMe] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);

  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [link, setLink] = useState("");
  const [level, setLevel] = useState<"info" | "warning" | "promo">("promo");
  const [audience, setAudience] = useState<"all" | "missing_email" | "plan" | "users">("missing_email");
  const [audienceValue, setAudienceValue] = useState("");
  const [targetUsernames, setTargetUsernames] = useState("");
  const [startsAt, setStartsAt] = useState("");
  const [endsAt, setEndsAt] = useState("");

  const [sending, setSending] = useState(false);

  useEffect(() => {
    const token = getToken();
    if (!token) {
      navigate("/auth");
      return;
    }

    (async () => {
      try {
        const user = await authApi.getMe();
        setMe(user);
      } catch {
        toast.error("Не удалось загрузить профиль");
        setMe(null);
      } finally {
        setLoading(false);
      }
    })();
  }, [navigate]);

  const isStaff = useMemo(() => {
    const role = (me?.role || "user").toLowerCase();
    return role !== "user";
  }, [me]);

  const canSend = title.trim().length > 0 && body.trim().length > 0;

  const handleSend = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!canSend) return;

    setSending(true);
    try {
      const req: any = {
        title: title.trim(),
        body: body.trim(),
        audience,
        level,
      };

      if (link.trim()) req.link = link.trim();
      if (startsAt.trim()) req.starts_at = startsAt.trim();
      if (endsAt.trim()) req.ends_at = endsAt.trim();

      if (audience === "plan") {
        if (!audienceValue.trim()) {
          toast.error("Укажите tariff id (audience_value)");
          return;
        }
        req.audience_value = audienceValue.trim();
      }

      if (audience === "users") {
        const names = targetUsernames
          .split(/[,\n]/g)
          .map((s) => s.trim())
          .filter(Boolean);
        if (!names.length) {
          toast.error("Укажите usernames для audience=users");
          return;
        }
        req.target_usernames = names;
      }

      const resp = await adminApi.createNotification(req);
      toast.success(`Отправлено (id: ${resp.id})`);
      setTitle("");
      setBody("");
      setLink("");
      setAudienceValue("");
      setTargetUsernames("");
      setStartsAt("");
      setEndsAt("");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Ошибка отправки");
    } finally {
      setSending(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  if (!isStaff) {
    return (
      <div className="min-h-screen">
        <Header isLoggedIn={true} />
        <main className="pt-32 pb-20 px-4">
          <div className="container mx-auto max-w-2xl">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <ShieldAlert className="h-5 w-5 text-primary" />
                  Доступ запрещён
                </CardTitle>
                <CardDescription>Требуется роль staff/admin/superadmin.</CardDescription>
              </CardHeader>
              <CardContent>
                <Button variant="outline" onClick={() => navigate("/profile")}>Назад в профиль</Button>
              </CardContent>
            </Card>
          </div>
        </main>
        <Footer />
      </div>
    );
  }

  return (
    <div className="min-h-screen">
      <Header isLoggedIn={true} />

      <main className="pt-32 pb-20 px-4">
        <div className="container mx-auto max-w-2xl space-y-8">
          <Card className="animate-fade-in">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <BellRing className="h-5 w-5 text-primary" />
                Рассылка уведомлений
              </CardTitle>
              <CardDescription>
                Создаёт уведомление для пользователей приложения.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleSend} className="space-y-5">
                <div className="space-y-2">
                  <Label>Заголовок</Label>
                  <Input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Скидка за email" disabled={sending} />
                </div>

                <div className="space-y-2">
                  <Label>Текст</Label>
                  <Textarea value={body} onChange={(e) => setBody(e.target.value)} placeholder="Добавьте email в Профиле и получите скидку." disabled={sending} rows={5} />
                </div>

                <div className="space-y-2">
                  <Label>Ссылка (опционально)</Label>
                  <Input value={link} onChange={(e) => setLink(e.target.value)} placeholder="https://ttboost.pro" disabled={sending} />
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label>Тип</Label>
                    <Select value={level} onValueChange={(v) => setLevel(v as any)}>
                      <SelectTrigger>
                        <SelectValue placeholder="promo" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="promo">promo</SelectItem>
                        <SelectItem value="info">info</SelectItem>
                        <SelectItem value="warning">warning</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>

                  <div className="space-y-2">
                    <Label>Аудитория</Label>
                    <Select value={audience} onValueChange={(v) => setAudience(v as any)}>
                      <SelectTrigger>
                        <SelectValue placeholder="missing_email" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="missing_email">missing_email</SelectItem>
                        <SelectItem value="all">all</SelectItem>
                        <SelectItem value="plan">plan</SelectItem>
                        <SelectItem value="users">users</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>

                {audience === "plan" && (
                  <div className="space-y-2">
                    <Label>Tariff ID(s) (через запятую)</Label>
                    <Input
                      value={audienceValue}
                      onChange={(e) => setAudienceValue(e.target.value)}
                      placeholder="nova_streamer_one_mobile,nova_streamer_duo"
                      disabled={sending}
                    />
                  </div>
                )}

                {audience === "users" && (
                  <div className="space-y-2">
                    <Label>Usernames (через запятую или с новой строки)</Label>
                    <Textarea
                      value={targetUsernames}
                      onChange={(e) => setTargetUsernames(e.target.value)}
                      placeholder="demoGoogle\nstreamer123"
                      disabled={sending}
                      rows={4}
                    />
                  </div>
                )}

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label>Starts at (ISO, опционально)</Label>
                    <Input value={startsAt} onChange={(e) => setStartsAt(e.target.value)} placeholder="2025-12-25T10:00:00" disabled={sending} />
                  </div>
                  <div className="space-y-2">
                    <Label>Ends at (ISO, опционально)</Label>
                    <Input value={endsAt} onChange={(e) => setEndsAt(e.target.value)} placeholder="2026-01-01T00:00:00" disabled={sending} />
                  </div>
                </div>

                <Button type="submit" variant="gold" className="w-full" disabled={sending || !canSend}>
                  {sending ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin" />
                      Отправка...
                    </>
                  ) : (
                    "Отправить уведомление"
                  )}
                </Button>

                <p className="text-xs text-muted-foreground">
                  Совет: для кейса “добавьте email — получите скидку” выберите audience = <span className="font-mono">missing_email</span>.
                </p>
              </form>
            </CardContent>
          </Card>
        </div>
      </main>

      <Footer />
    </div>
  );
};

export default AdminNotifications;
