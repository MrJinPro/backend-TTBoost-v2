import { useMemo, useState } from "react";
import { Header } from "@/components/Header";
import { Footer } from "@/components/Footer";
import { Button } from "@/components/ui/button";

type Lang = "ru" | "en";

const Privacy = () => {
  const [lang, setLang] = useState<Lang>("ru");

  const content = useMemo(() => {
    if (lang === "en") {
      return {
        title: "Privacy Policy",
        updated: "Last updated: 22 December 2025",
        body: (
          <>
            <p className="text-muted-foreground">
              This Privacy Policy explains how NovaBoost collects, uses, and protects information when you use our
              website and services.
            </p>

            <h2 className="mt-8 text-xl font-semibold">1. Information We Collect</h2>
            <ul className="mt-2 list-disc pl-5 text-muted-foreground">
              <li>Account data: username and authentication identifiers.</li>
              <li>Profile data you provide: email address and avatar (optional).</li>
              <li>Technical data: device/browser information, IP address, logs, and diagnostic data.</li>
              <li>Usage data: actions within the service (e.g., settings and feature usage).</li>
            </ul>

            <h2 className="mt-8 text-xl font-semibold">2. Payments and Subscriptions</h2>
            <p className="mt-2 text-muted-foreground">
              Payments for mobile subscriptions are processed by Google Play (Android) and Apple App Store (iOS). We
              may receive purchase/receipt verification data and subscription status from these platforms to provide
              access to paid features.
            </p>

            <h2 className="mt-8 text-xl font-semibold">3. How We Use Information</h2>
            <ul className="mt-2 list-disc pl-5 text-muted-foreground">
              <li>To provide and operate the service (authentication, features, support).</li>
              <li>To verify subscriptions and manage access to paid plans.</li>
              <li>To improve reliability and security, prevent abuse, and debug issues.</li>
              <li>To communicate with you about important updates and support requests.</li>
            </ul>

            <h2 className="mt-8 text-xl font-semibold">4. Sharing of Information</h2>
            <p className="mt-2 text-muted-foreground">
              We do not sell your personal data. We may share data with service providers only as necessary to run the
              service (e.g., hosting, logging, payment platform verification) and when required by law.
            </p>

            <h2 className="mt-8 text-xl font-semibold">5. Data Retention</h2>
            <p className="mt-2 text-muted-foreground">
              We retain information for as long as needed to provide the service, comply with legal obligations, and
              resolve disputes. You may request deletion subject to applicable requirements.
            </p>

            <h2 className="mt-8 text-xl font-semibold">6. Security</h2>
            <p className="mt-2 text-muted-foreground">
              We take reasonable measures to protect your information. However, no method of transmission or storage
              is 100% secure.
            </p>

            <h2 className="mt-8 text-xl font-semibold">7. Your Rights</h2>
            <p className="mt-2 text-muted-foreground">
              Depending on your location, you may have rights to access, correct, or delete your personal data. To
              exercise these rights, contact us.
            </p>

            <h2 className="mt-8 text-xl font-semibold">8. Contact</h2>
            <p className="mt-2 text-muted-foreground">
              For privacy questions, contact: <span className="text-foreground">dev@mrjin.pro</span>
            </p>
          </>
        ),
      };
    }

    return {
      title: "Политика конфиденциальности",
      updated: "Последнее обновление: 22 декабря 2025",
      body: (
        <>
          <p className="text-muted-foreground">
            Настоящая Политика конфиденциальности объясняет, как NovaBoost собирает, использует и защищает
            информацию при использовании сайта и сервисов.
          </p>

          <h2 className="mt-8 text-xl font-semibold">1. Какие данные мы собираем</h2>
          <ul className="mt-2 list-disc pl-5 text-muted-foreground">
            <li>Данные аккаунта: имя пользователя и идентификаторы аутентификации.</li>
            <li>Данные профиля, которые вы указываете: email и аватар (опционально).</li>
            <li>Технические данные: сведения об устройстве/браузере, IP-адрес, логи и диагностические данные.</li>
            <li>Данные использования: действия в сервисе (например, настройки и использование функций).</li>
          </ul>

          <h2 className="mt-8 text-xl font-semibold">2. Платежи и подписки</h2>
          <p className="mt-2 text-muted-foreground">
            Оплата мобильных подписок обрабатывается Google Play (Android) и Apple App Store (iOS). Мы можем
            получать данные для проверки покупки/квитанции и статус подписки, чтобы предоставлять доступ к
            платным функциям.
          </p>

          <h2 className="mt-8 text-xl font-semibold">3. Как мы используем данные</h2>
          <ul className="mt-2 list-disc pl-5 text-muted-foreground">
            <li>Для предоставления и работы сервиса (вход, функции, поддержка).</li>
            <li>Для проверки подписок и управления доступом к платным тарифам.</li>
            <li>Для повышения надежности и безопасности, предотвращения злоупотреблений и отладки.</li>
            <li>Для связи с вами по важным обновлениям и запросам в поддержку.</li>
          </ul>

          <h2 className="mt-8 text-xl font-semibold">4. Передача данных третьим лицам</h2>
          <p className="mt-2 text-muted-foreground">
            Мы не продаем персональные данные. Мы можем передавать данные только тем поставщикам услуг, которым это
            необходимо для работы сервиса (например, хостинг, логирование, проверка платежей), а также в случаях,
            когда это требуется законом.
          </p>

          <h2 className="mt-8 text-xl font-semibold">5. Хранение данных</h2>
          <p className="mt-2 text-muted-foreground">
            Мы храним данные столько, сколько это необходимо для предоставления сервиса, выполнения юридических
            обязательств и разрешения споров. Вы можете запросить удаление данных с учетом применимых требований.
          </p>

          <h2 className="mt-8 text-xl font-semibold">6. Безопасность</h2>
          <p className="mt-2 text-muted-foreground">
            Мы принимаем разумные меры защиты. Однако ни один способ передачи или хранения не гарантирует 100%
            безопасность.
          </p>

          <h2 className="mt-8 text-xl font-semibold">7. Ваши права</h2>
          <p className="mt-2 text-muted-foreground">
            В зависимости от вашей страны у вас могут быть права на доступ, исправление или удаление персональных
            данных. Чтобы воспользоваться правами, свяжитесь с нами.
          </p>

          <h2 className="mt-8 text-xl font-semibold">8. Контакты</h2>
          <p className="mt-2 text-muted-foreground">
            По вопросам конфиденциальности: <span className="text-foreground">dev@mrjin.pro</span>
          </p>
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
            <div>
              <h1 className="text-3xl font-bold text-foreground">{content.title}</h1>
              <p className="mt-2 text-sm text-muted-foreground">{content.updated}</p>
            </div>
            <div className="flex items-center gap-2">
              <Button variant={lang === "ru" ? "default" : "outline"} size="sm" onClick={() => setLang("ru")}>
                RU
              </Button>
              <Button variant={lang === "en" ? "default" : "outline"} size="sm" onClick={() => setLang("en")}>
                EN
              </Button>
            </div>
          </div>

          <div className="mt-8 space-y-4">{content.body}</div>
        </div>
      </main>

      <Footer />
    </div>
  );
};

export default Privacy;
