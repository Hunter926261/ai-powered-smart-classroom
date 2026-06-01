import ThemeToggle from "./ThemeToggle";

const Navbar = () => {
  return (
    <div className="flex justify-between items-center p-4 border-b dark:border-slate-700">
      <h2 className="text-2xl font-semibold">
        Smart Classroom Dashboard
      </h2>

      <ThemeToggle />
    </div>
  );
};

export default Navbar;