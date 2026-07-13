import "./globals.css";

export const metadata = {
  title: "Adhikar.AI — Agentic Copilot for Government Schemes",
  description:
    "An agentic AI copilot that helps CSC operators in rural India extract citizen data, match government welfare schemes, and generate localized document checklists.",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
