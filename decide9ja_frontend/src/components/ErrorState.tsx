export default function ErrorState({
  message = "Failed to load data",
  onRetry,
}: {
  message?: string;
  onRetry?: () => void;
}) {
  return (
    <div className="flex flex-col items-center justify-center py-16 gap-4">
      <div className="w-12 h-12 bg-c-red/10 rounded-full flex items-center justify-center">
        <span className="text-c-red text-xl">!</span>
      </div>
      <span className="text-sm text-gray-600">{message}</span>
      {onRetry && (
        <button
          onClick={onRetry}
          className="text-sm font-mono bg-c-black text-white px-4 py-2 hover:bg-gray-800 transition-colors"
        >
          Retry
        </button>
      )}
    </div>
  );
}
