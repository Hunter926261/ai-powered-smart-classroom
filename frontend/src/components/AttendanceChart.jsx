import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from "recharts";

const data = [
  { day: "Mon", attendance: 18 },
  { day: "Tue", attendance: 15 },
  { day: "Wed", attendance: 20 },
  { day: "Thu", attendance: 17 },
  { day: "Fri", attendance: 19 },
];

const AttendanceChart = () => {
  return (
    <div className="bg-white dark:bg-slate-800 rounded-2xl p-5 shadow-md h-[350px]">
      <h2 className="text-xl font-semibold mb-5">
        Attendance Overview
      </h2>

      <ResponsiveContainer width="100%" height="80%">
        <LineChart data={data}>
          <XAxis dataKey="day" />
          <YAxis />
          <Tooltip />

          <Line
            type="monotone"
            dataKey="attendance"
            stroke="#3B82F6"
            strokeWidth={3}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
};

export default AttendanceChart;