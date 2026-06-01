const RecognitionFeed = () => {
  const logs = [
    "Rahul detected",
    "Priya entered",
    "Unknown face",
    "Atharva detected",
  ];

  return (
    <div className="bg-white dark:bg-slate-800 rounded-2xl p-5 shadow-md h-[400px]">
      <h2 className="text-xl font-semibold mb-4">
        Recognition Feed
      </h2>

      <div className="space-y-3">
        {logs.map((log, index) => (
          <div
            key={index}
            className="p-3 bg-slate-100 dark:bg-slate-700 rounded-lg"
          >
            {log}
          </div>
        ))}
      </div>
    </div>
  );
};

export default RecognitionFeed;