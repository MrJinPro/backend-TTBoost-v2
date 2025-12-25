import { Link } from "react-router-dom";

const footerLinks = [
  { to: "/", label: "Главная" },
  { to: "/profile", label: "Профиль" },
  { to: "/auth", label: "Войти" },
  { to: "/contact", label: "Контакты" },
  { to: "/privacy", label: "Конфиденциальность" },
  { to: "/terms", label: "Условия" },
  { to: "/account-delete", label: "Удаление аккаунта" },
];

export const Footer = () => {
  return (
    <footer className="mt-auto py-10 px-4 border-t border-border/30">
      <div className="container mx-auto">
        <nav className="flex flex-wrap items-center justify-center gap-x-5 gap-y-2">
          {footerLinks.map((l) => (
            <Link
              key={l.to}
              to={l.to}
              className="text-sm text-muted-foreground hover:text-foreground transition-colors"
            >
              {l.label}
            </Link>
          ))}
        </nav>

        <p className="mt-6 text-center text-xs text-muted-foreground">
          © {new Date().getFullYear()} NovaBoost. Все права защищены.
        </p>
      </div>
    </footer>
  );
};
