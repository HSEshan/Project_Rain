import React, { useEffect, useState } from "react";
import logo from "./logo.svg";
import "./App.css";
import apiClient from "./utils/apiClient";

function App() {
  const [response, setResponse] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    apiClient
      .get("/")
      .then((res) => {
        console.log("Backend response:", res); // <-- log full axios response
        setResponse(res.data); // assuming backend sends { status: "OK" }
      })
      .catch((err) => {
        console.error("Error fetching data:", err); // <-- log error details
        setError(err.message || "Error fetching data");
      });
  }, []);

  return (
    <div className="App">
      <header className="App-header">
        <img src={logo} className="App-logo" alt="logo" />
        <p>
          Edit <code>src/App.js</code> and save to reload.
        </p>
        <a
          className="App-link"
          href="https://reactjs.org"
          target="_blank"
          rel="noopener noreferrer"
        >
          Learn React
        </a>
        <h1 className="text-3xl font-bold underline">
          Hello world! (Testing Tailwind)
        </h1>
        <div className="max-w-md min-w-[300px] mx-auto my-8 p-6 bg-gradient-to-r from-purple-500 via-pink-500 to-red-500 rounded-2xl shadow-lg transform transition duration-300 hover:scale-105">
          <h2 className="text-white text-xl font-bold mb-4">
            Backend Response
          </h2>

          {response ? (
            <div className="max-w-[150px] mx-auto bg-white rounded-lg p-1 shadow-inner">
              <p className="text-gray-700">
                <span className="font-semibold">Status:</span> {response.status}
              </p>
            </div>
          ) : (
            <p className="text-white">Loading...</p>
          )}
        </div>
      </header>
    </div>
  );
}

export default App;
