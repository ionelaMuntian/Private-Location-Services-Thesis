import { AppRouter } from "./app/router";

function App() {
  return (
    <>
      <div className="app-band app-band-top" />
      <div className="app-content">
        <AppRouter />
      </div>
      <div className="app-band app-band-bottom" />
    </>
  );
}

export default App;