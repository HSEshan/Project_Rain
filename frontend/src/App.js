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
        <h2>
          Response from Backend ={" "}
          {response ? JSON.stringify(response) : "Loading..."}
        </h2>
      </header>
    </div>
  );
}

export default App;
