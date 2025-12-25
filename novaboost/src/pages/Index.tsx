import { Header } from "@/components/Header";
import { Footer } from "@/components/Footer";
import { Link } from "react-router-dom";
import starLogo from "@/assets/star-logo.png";
import { Sparkles, Zap, Shield } from "lucide-react";

const Index = () => {
  return (
    <div className="min-h-screen">
      <Header />
      
      {/* Hero Section */}
      <section className="pt-32 pb-20 px-4">
        <div className="container mx-auto text-center">
          <div className="animate-fade-in">
            <img 
              src={starLogo} 
              alt="NovaBoost" 
              className="h-24 w-24 mx-auto mb-8 animate-float"
            />
            <h1 className="text-4xl md:text-6xl font-bold mb-6">
              <span className="text-gradient-gold">NovaBoost</span>
              <br />
              <span className="text-foreground">Стриминг нового уровня</span>
            </h1>
            <p className="text-lg md:text-xl text-muted-foreground max-w-2xl mx-auto mb-12">
              Инструменты для озвучки и алёртов во время LIVE‑эфиров: TTS, подарки, триггеры и виджеты.
            </p>
          </div>

          {/* Features */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 max-w-4xl mx-auto mb-20">
            {[
              { icon: Zap, title: 'Мгновенный эффект', desc: 'Результаты с первой минуты' },
              { icon: Shield, title: 'Безопасность', desc: 'Защита вашего аккаунта' },
              { icon: Sparkles, title: 'Авто-режим', desc: 'Работает 24/7 без участия' },
            ].map((feature, idx) => (
              <div 
                key={idx} 
                className={`flex flex-col items-center p-6 rounded-2xl bg-card/50 border border-border/30 animate-fade-in-delay-${idx + 1}`}
              >
                <feature.icon className="h-10 w-10 text-primary mb-4" />
                <h3 className="font-semibold text-foreground mb-2">{feature.title}</h3>
                <p className="text-sm text-muted-foreground">{feature.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="py-16 px-4">
        <div className="container mx-auto max-w-4xl">
          <div className="text-center mb-10">
            <h2 className="text-2xl md:text-3xl font-bold text-foreground mb-3">Ссылки</h2>
            <p className="text-muted-foreground">Профиль и обязательные страницы для магазинов приложений.</p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {[
              { to: "/profile", title: "Профиль", desc: "Управление аккаунтом и лицензией" },
              { to: "/privacy", title: "Конфиденциальность", desc: "Privacy Policy" },
              { to: "/terms", title: "Условия", desc: "Terms of Use" },
              { to: "/contact", title: "Контакты", desc: "Поддержка и разработчик" },
              { to: "/account-delete", title: "Удаление аккаунта", desc: "Инструкция удаления" },
              { to: "/auth", title: "Войти", desc: "Вход в аккаунт" },
            ].map((l) => (
              <Link
                key={l.to}
                to={l.to}
                className="block rounded-2xl bg-card/50 border border-border/30 p-6 hover:border-primary/50 transition-all duration-300"
              >
                <div className="font-semibold text-foreground">{l.title}</div>
                <div className="mt-2 text-sm text-muted-foreground">{l.desc}</div>
              </Link>
            ))}
          </div>
        </div>
      </section>

      <Footer />
    </div>
  );
};

export default Index;
