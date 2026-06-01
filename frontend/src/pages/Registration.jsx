import { useState } from "react";
import axios from "axios";

const Registration = () => {

  const [name, setName] = useState("");

  const registerStudent = async () => {

    if (!name) {
      alert("Enter student name");
      return;
    }

    try {

      const formData = new FormData();

      formData.append("name", name);

      const response = await axios.post(
        "http://127.0.0.1:8000/register_face",
        formData
      );

      alert(response.data.message);

      setName("");

    } catch (error) {

      console.log(error);

      alert("Registration failed");
    }
  };

  return (
    <div className="p-8 text-white">

      <h1 className="text-4xl font-bold mb-8">
        Student Registration
      </h1>

      <div className="bg-slate-800 p-6 rounded-2xl w-[420px]">

        <input
          type="text"
          placeholder="Enter Student Name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          className="w-full p-4 rounded-xl text-black mb-4"
        />

        <button
          onClick={registerStudent}
          className="w-full bg-blue-600 hover:bg-blue-700 p-4 rounded-xl"
        >
          Register Student
        </button>

      </div>
    </div>
  );
};

export default Registration;