import Sidebar from "../components/Sidebar";
import Navbar from "../components/Navbar";

const MainLayout = ({ children }) => {
  return (
    <div className="flex bg-slate-100 dark:bg-slate-900 min-h-screen text-black dark:text-white">
      <Sidebar />

      <div className="flex-1">
        <Navbar />

        <div className="p-5">
          {children}
        </div>
      </div>
    </div>
  );
};

export default MainLayout;