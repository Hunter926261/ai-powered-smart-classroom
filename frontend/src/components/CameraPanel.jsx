const CameraPanel = () => {

  return (
    <div className="bg-white dark:bg-slate-800 rounded-2xl p-5 shadow-md">

      <h2 className="text-xl font-semibold mb-4">
        Live Camera
      </h2>

      <div className="rounded-xl overflow-hidden">

        <img
          src="http://127.0.0.1:8000/video_feed"
          alt="Camera Stream"
          className="w-full rounded-xl"
        />

      </div>
    </div>
  );
};

export default CameraPanel;