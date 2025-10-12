import type React from "react"
import "./globals.css"

export const metadata = {
  title: "MetaDAO Support Bot",
  description: "Telegram support bot for MetaDAO",
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  )
}
