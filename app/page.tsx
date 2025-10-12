export default function Home() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-blue-50 to-indigo-100">
      <div className="text-center">
        <h1 className="text-4xl font-bold text-gray-900 mb-4">MetaDAO Support Bot</h1>
        <p className="text-lg text-gray-600 mb-2">Bot is running and ready to receive webhooks</p>
        <p className="text-sm text-gray-500">
          Webhook endpoint: <code className="bg-gray-200 px-2 py-1 rounded">/api/MetaDAOBot</code>
        </p>
      </div>
    </div>
  )
}
