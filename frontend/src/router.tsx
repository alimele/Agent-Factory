import { createBrowserRouter, Navigate } from "react-router-dom";
import Layout from "./Layout";
import Start from "./pages/Start";
import Configure from "./pages/Configure";
import ReviewLaunch from "./pages/ReviewLaunch";
import MyAgents from "./pages/MyAgents";
import Playground from "./pages/Playground";
import AdminKnowledgeSources from "./pages/AdminKnowledgeSources";
import AdminAgentTemplates from "./pages/AdminAgentTemplates";

export const router = createBrowserRouter([
  {
    path: "/",
    element: <Layout />,
    children: [
      { index: true, element: <Navigate to="start" replace /> },
      { path: "start", element: <Start /> },
      { path: "configure", element: <Configure /> },
      { path: "launch", element: <ReviewLaunch /> },
      { path: "my-agents", element: <MyAgents /> },
      { path: "playground", element: <Playground /> },
      { path: "admin/knowledge-sources", element: <AdminKnowledgeSources /> },
      { path: "admin/agent-templates", element: <AdminAgentTemplates /> },
    ],
  },
]);
