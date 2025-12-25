import { useMemo, useState } from "react";
import { Header } from "@/components/Header";
import { Footer } from "@/components/Footer";
import { Button } from "@/components/ui/button";

type Lang = "ru" | "en";

const Contact = () => {
  const [lang, setLang] = useState<Lang>("ru");

  const content = useMemo(() => {
    if (lang === "en") {
      return {
        title: "Contacts",
        body: (
          <>
            <p className="text-muted-foreground">You can reach us using the contacts below.</p>
            <div className="mt-6 space-y-3">
              <div>
                <div className="text-sm text-muted-foreground">Developer</div>
                <div className="text-foreground">dev@mrjin.pro</div>
              </div>
              <div>
                <div className="text-sm text-muted-foreground">Support</div>
                <div className="text-foreground">support@novaboost.cloud</div>
              </div>
            </div>
          </>
        ),
      };
    }

    return {
      title: "Контакты",
      body: (
        <>
          <p className="text-muted-foreground">Свяжитесь с нами по контактам ниже.</p>
          <div className="mt-6 space-y-3">
            <div>
              <div className="text-sm text-muted-foreground">Разработчик</div>
              <div className="text-foreground">dev@mrjin.pro</div>
            </div>
            <div>
              <div className="text-sm text-muted-foreground">Тех поддержка</div>
              <div className="text-foreground">support@novaboost.cloud</div>
            </div>
          </div>
        </>
      ),
    };
  }, [lang]);

  return (
    <div className="min-h-screen">
      <Header />
      <main className="pt-24 pb-16 px-4">
        <div className="container mx-auto max-w-3xl">
          <div className="flex items-center justify-between gap-4">
            <h1 className="text-3xl font-bold text-foreground">{content.title}</h1>
            <div className="flex items-center gap-2">
              <Button variant={lang === "ru" ? "default" : "outline"} size="sm" onClick={() => setLang("ru")}>
                RU
              </Button>
              <Button variant={lang === "en" ? "default" : "outline"} size="sm" onClick={() => setLang("en")}>
                EN
              </Button>
            </div>
          </div>

          <div className="mt-8">{content.body}</div>
        </div>
      </main>

      <Footer />
    </div>
  );
};

export default Contact;
