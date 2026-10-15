import { AuthenticatedTemplate, UnauthenticatedTemplate, useMsal } from "@azure/msal-react";
import { RouterProvider } from "react-router-dom";
import { loginRequest } from "./authConfig";
import { router } from "./router";
import { BlueprintProvider } from "./BlueprintContext";
import { useEffect, useState } from "react";
import "./theme.css";

export default function App() {
  const { instance, accounts } = useMsal();
  const [signingIn, setSigningIn] = useState(false);
  const handleLogin = () => {
    setSigningIn(true);
    instance.loginRedirect(loginRequest).catch((e) => {
      console.error(e);
      setSigningIn(false);
    });
  };

  useEffect(() => {
    if (!instance.getActiveAccount() && accounts.length > 0) instance.setActiveAccount(accounts[0]);
  }, [instance, accounts]);

  return <>
    <AuthenticatedTemplate><BlueprintProvider><RouterProvider router={router} /></BlueprintProvider></AuthenticatedTemplate>
    <UnauthenticatedTemplate>
      <main className="signinShell">
        <div className="signinBackdrop" aria-hidden="true"><span /><span /><span /></div>
        <section className="signinCard">
          <div className="signinBrand"><div className="signinLogo">C</div><div><strong>CREDO</strong><small>ENTERPRISE AI</small></div></div>
          <div className="signinRule" />
          <p className="eyebrow">GOVERNED AGENT BUILDER</p>
          <h1>Build enterprise agents<br /><span>with confidence.</span></h1>
          <p className="signinIntro">Design, configure, and review AI agents using approved enterprise knowledge, tools, and access controls.</p>
          <div className="signinFeatures"><div><span>01</span><p><strong>Configure</strong><small>Define purpose, knowledge, and behavior</small></p></div><div><span>02</span><p><strong>Govern</strong><small>Set access and review policy checks</small></p></div><div><span>03</span><p><strong>Validate</strong><small>Review the blueprint before deployment</small></p></div></div>
          <button className="signinButton" onClick={handleLogin} disabled={signingIn}><span className="microsoftMark" aria-hidden="true"><i /><i /><i /><i /></span>{signingIn ? "Redirecting to Microsoft…" : "Sign in with Microsoft"}<span className="signinArrow">→</span></button>
          <p className="signinFoot"><span className="lockMark">▣</span> Access is restricted to your organization account.</p>
        </section>
        <footer className="signinFooter">CREDO Agent Factory <span>•</span> Enterprise AI governance</footer>
      </main>
    </UnauthenticatedTemplate>
  </>;
}