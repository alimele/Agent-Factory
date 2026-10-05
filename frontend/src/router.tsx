import { createBrowserRouter, Navigate } from "react-router-dom";
import Layout from "./Layout";
import Describe from "./pages/Describe";
import Context from "./pages/Context";
import Knowledge from "./pages/Knowledge";
import Tools from "./pages/Tools";
import Behavior from "./pages/Behavior";
import Security from "./pages/Security";
import Review from "./pages/Review";
import Test from "./pages/Test";
import Submit from "./pages/Submit";
import Lifecycle from "./pages/Lifecycle";

export const router = createBrowserRouter([
  {
    path: "/",
    element: <Layout />,
    children: [
      { index: true, element: <Navigate to="describe" replace /> },
      { path: "describe", element: <Describe /> },
      { path: "context", element: <Context /> },
      { path: "knowledge", element: <Knowledge /> },
      { path: "tools", element: <Tools /> },
      { path: "behavior", element: <Behavior /> },
      { path: "security", element: <Security /> },
      { path: "review", element: <Review /> },
      { path: "test", element: <Test /> },
      { path: "submit", element: <Submit /> },
      { path: "lifecycle", element: <Lifecycle /> },
    ],
  },
]);