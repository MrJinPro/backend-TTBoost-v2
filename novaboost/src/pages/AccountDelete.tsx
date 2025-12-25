import { useMemo, useState } from "react";
import { Header } from "@/components/Header";
import { Footer } from "@/components/Footer";
import { Button } from "@/components/ui/button";

type Lang = "ru" | "en";

const AccountDelete = () => {
  const [lang, setLang] = useState<Lang>("ru");

  const content = useMemo(() => {
    if (lang === "en") {
      return {
        title: "NovaBoost Account Deletion",
        updated: "Last updated: 24 December 2025",
        body: (
          <>
            <p className="text-muted-foreground">
              You can delete your NovaBoost account and associated data from within the NovaBoost Mobile app.
            </p>

            <h2 className="mt-8 text-xl font-semibold">How to delete your account</h2>
            <ol className="mt-2 list-decimal pl-5 text-muted-foreground">
              <li>Open NovaBoost Mobile</li>
              <li>Settings → Account → Delete account</li>
              <li>Confirm deletion (you will be asked to type <span className="text-foreground">DELETE</span>)</li>
            </ol>

            <h2 className="mt-8 text-xl font-semibold">What happens after confirmation</h2>
            <ul className="mt-2 list-disc pl-5 text-muted-foreground">
              <li>Your account is deleted.</li>
              <li>Your user data is deleted from our server.</li>
              <li>Deletion timeframe: up to 30 days.</li>
            </ul>

            <h2 className="mt-8 text-xl font-semibold">Data included in deletion</h2>
            <p className="mt-2 text-muted-foreground">
              This typically includes account/profile data and app-related settings/content stored on our servers (for
              example: profile info, settings, triggers, uploaded media such as avatar/sounds/tts artifacts).
            </p>

            <h2 className="mt-8 text-xl font-semibold">Notes</h2>
            <p className="mt-2 text-muted-foreground">
              In some cases, limited information may be retained longer if required to comply with law, prevent fraud,
              or resolve payment disputes.
            </p>

            <h2 className="mt-8 text-xl font-semibold">Contact</h2>
            <p className="mt-2 text-muted-foreground">
              If you cannot access the app and need help with account deletion, contact:
              <span className="text-foreground"> support@novaboost.cloud</span>
            </p>
          </>
        ),
      };
    }

    return {
      title: "Удаление аккаунта NovaBoost",
      updated: "Последнее обновление: 24 декабря 2025",
      body: (
        <>
          <p className="text-muted-foreground">
            Пользователь может удалить аккаунт NovaBoost и связанные с ним данные прямо в приложении NovaBoost Mobile.
          </p>

          <h2 className="mt-8 text-xl font-semibold">Как удалить аккаунт</h2>
          <ol className="mt-2 list-decimal pl-5 text-muted-foreground">
            <li>Откройте NovaBoost Mobile</li>
            <li>Профиль → Аккаунт → Удалить аккаунт</li>
            <li>
              Подтвердите удаление (нужно ввести <span className="text-foreground">DELETE</span>)
            </li>
          </ol>

          <h2 className="mt-8 text-xl font-semibold">После подтверждения</h2>
          <ul className="mt-2 list-disc pl-5 text-muted-foreground">
            <li>Аккаунт удаляется.</li>
            <li>Данные пользователя удаляются с сервера.</li>
            <li>Срок удаления — до 30 дней.</li>
          </ul>

          <h2 className="mt-8 text-xl font-semibold">Какие данные удаляются</h2>
          <p className="mt-2 text-muted-foreground">
            Обычно это включает данные аккаунта/профиля и связанные с приложением настройки/контент, хранящиеся на
            наших серверах (например: данные профиля, настройки, триггеры, загруженные медиа — аватар/звуки/tts).
          </p>

          <h2 className="mt-8 text-xl font-semibold">Примечания</h2>
          <p className="mt-2 text-muted-foreground">
            В отдельных случаях ограниченный набор данных может храниться дольше, если это требуется законом, для
            предотвращения мошенничества или для урегулирования платежных споров.
          </p>

          <h2 className="mt-8 text-xl font-semibold">Контакты</h2>
          <p className="mt-2 text-muted-foreground">
            Если вы не можете войти в приложение и нужна помощь с удалением, напишите:
            <span className="text-foreground"> support@novaboost.cloud</span>
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

export default AccountDelete;
