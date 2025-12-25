import { useMemo, useState } from "react";
import { Header } from "@/components/Header";
import { Footer } from "@/components/Footer";
import { Button } from "@/components/ui/button";

type Lang = "ru" | "en";

const Terms = () => {
  const [lang, setLang] = useState<Lang>("ru");

  const content = useMemo(() => {
    if (lang === "en") {
      return {
        title: "Terms of Use",
        updated: "Last updated: 22 December 2025",
        body: (
          <>
            <p className="text-muted-foreground">
              These Terms of Use govern your access to and use of NovaBoost website, applications, and services.
              By using the service, you agree to these Terms.
            </p>

            <h2 className="mt-8 text-xl font-semibold">1. Account</h2>
            <p className="mt-2 text-muted-foreground">
              You are responsible for maintaining the confidentiality of your account credentials and for all
              activities under your account.
            </p>

            <h2 className="mt-8 text-xl font-semibold">2. Subscriptions and Billing</h2>
            <p className="mt-2 text-muted-foreground">
              Paid access may be offered via subscriptions on Google Play (Android) and Apple App Store (iOS).
              Billing, renewals, cancellations, refunds, and charge disputes are handled according to the respective
              store’s terms and your store account settings.
            </p>

            <h2 className="mt-8 text-xl font-semibold">3. Acceptable Use</h2>
            <ul className="mt-2 list-disc pl-5 text-muted-foreground">
              <li>Do not use the service for illegal activities.</li>
              <li>Do not attempt to bypass limitations, security, or access controls.</li>
              <li>Do not abuse, disrupt, or overload the service.</li>
            </ul>

            <h2 className="mt-8 text-xl font-semibold">4. Availability</h2>
            <p className="mt-2 text-muted-foreground">
              The service may change over time. We may suspend or discontinue parts of the service at any time.
            </p>

            <h2 className="mt-8 text-xl font-semibold">5. Disclaimer</h2>
            <p className="mt-2 text-muted-foreground">
              The service is provided “as is” and “as available”. We do not guarantee uninterrupted or error-free
              operation.
            </p>

            <h2 className="mt-8 text-xl font-semibold">6. Limitation of Liability</h2>
            <p className="mt-2 text-muted-foreground">
              To the maximum extent permitted by applicable law, we are not liable for indirect or consequential
              damages arising from your use of the service.
            </p>

            <h2 className="mt-8 text-xl font-semibold">7. Termination</h2>
            <p className="mt-2 text-muted-foreground">
              We may suspend or terminate access if you violate these Terms or if required for security or legal
              reasons.
            </p>

            <h2 className="mt-8 text-xl font-semibold">8. Contact</h2>
            <p className="mt-2 text-muted-foreground">
              Questions about these Terms: <span className="text-foreground">support@novaboost.cloud</span>
            </p>
          </>
        ),
      };
    }

    return {
      title: "Условия использования",
      updated: "Последнее обновление: 22 декабря 2025",
      body: (
        <>
          <p className="text-muted-foreground">
            Настоящие Условия использования регулируют доступ и использование сайта, приложений и сервисов NovaBoost.
            Используя сервис, вы соглашаетесь с этими Условиями.
          </p>

          <h2 className="mt-8 text-xl font-semibold">1. Аккаунт</h2>
          <p className="mt-2 text-muted-foreground">
            Вы несете ответственность за сохранность данных доступа и все действия, совершенные под вашим аккаунтом.
          </p>

          <h2 className="mt-8 text-xl font-semibold">2. Подписки и оплата</h2>
          <p className="mt-2 text-muted-foreground">
            Платный доступ может предоставляться по подписке через Google Play (Android) и Apple App Store (iOS).
            Оплата, автопродление, отмена, возвраты и спорные списания регулируются правилами соответствующего
            магазина и настройками вашей учетной записи в магазине.
          </p>

          <h2 className="mt-8 text-xl font-semibold">3. Допустимое использование</h2>
          <ul className="mt-2 list-disc pl-5 text-muted-foreground">
            <li>Не используйте сервис для незаконных действий.</li>
            <li>Не пытайтесь обходить ограничения, безопасность или контроль доступа.</li>
            <li>Не злоупотребляйте сервисом и не нарушайте его работу.</li>
          </ul>

          <h2 className="mt-8 text-xl font-semibold">4. Доступность</h2>
          <p className="mt-2 text-muted-foreground">
            Сервис может изменяться. Мы можем приостанавливать или прекращать работу отдельных функций в любое время.
          </p>

          <h2 className="mt-8 text-xl font-semibold">5. Отказ от гарантий</h2>
          <p className="mt-2 text-muted-foreground">
            Сервис предоставляется «как есть» и «по мере доступности». Мы не гарантируем бесперебойную и безошибочную
            работу.
          </p>

          <h2 className="mt-8 text-xl font-semibold">6. Ограничение ответственности</h2>
          <p className="mt-2 text-muted-foreground">
            В пределах, разрешенных применимым законодательством, мы не несем ответственности за косвенные или
            последующие убытки, связанные с использованием сервиса.
          </p>

          <h2 className="mt-8 text-xl font-semibold">7. Прекращение доступа</h2>
          <p className="mt-2 text-muted-foreground">
            Мы можем ограничить или прекратить доступ при нарушении Условий, а также по причинам безопасности или
            по требованию закона.
          </p>

          <h2 className="mt-8 text-xl font-semibold">8. Контакты</h2>
          <p className="mt-2 text-muted-foreground">
            Вопросы по Условиям: <span className="text-foreground">support@novaboost.cloud</span>
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

export default Terms;
