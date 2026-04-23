/**
 * Copyright (c) Microsoft Corporation.
 * Licensed under the MIT license.
 */

import { render, screen, fireEvent } from "@testing-library/react";
import { FluentProvider, webLightTheme } from "@fluentui/react-components";
import Navigation, { GroupedNavigation } from "./Navigation";

const renderWithProvider = (ui: React.ReactElement) => {
  return render(<FluentProvider theme={webLightTheme}>{ui}</FluentProvider>);
};

describe("Navigation", () => {
  const defaultProps = {
    currentView: "chat" as const,
    onNavigate: jest.fn(),
    onToggleTheme: jest.fn(),
    isDarkMode: false,
  };

  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("renders compact quick access without cryptic page abbreviations", () => {
    renderWithProvider(<Navigation {...defaultProps} />);

    const chatButton = screen.getByTitle("Interactive Audit");
    expect(chatButton).toBeInTheDocument();
    expect(chatButton).not.toBeDisabled();
    expect(screen.queryByText("Gk")).not.toBeInTheDocument();
    expect(screen.queryByText("Rd")).not.toBeInTheDocument();
    expect(screen.queryByText("Ev")).not.toBeInTheDocument();
    expect(screen.queryByText("Hx")).not.toBeInTheDocument();
    expect(screen.queryByText("St")).not.toBeInTheDocument();
    expect(screen.queryByText("Bm")).not.toBeInTheDocument();
    expect(screen.queryByText("Fi")).not.toBeInTheDocument();
    expect(screen.queryByText("Pv")).not.toBeInTheDocument();
  });

  it("renders the configuration button", () => {
    renderWithProvider(<Navigation {...defaultProps} />);

    const configButton = screen.getByTitle("Configuration");
    expect(configButton).toBeInTheDocument();
  });

  it("calls onNavigate with 'chat' when chat button is clicked", () => {
    const onNavigate = jest.fn();
    renderWithProvider(
      <Navigation {...defaultProps} onNavigate={onNavigate} />
    );

    fireEvent.click(screen.getByTitle("Interactive Audit"));
    expect(onNavigate).toHaveBeenCalledWith("chat");
  });

  it("calls onNavigate with 'config' when config button is clicked", () => {
    const onNavigate = jest.fn();
    renderWithProvider(
      <Navigation {...defaultProps} onNavigate={onNavigate} />
    );

    fireEvent.click(screen.getByTitle("Configuration"));
    expect(onNavigate).toHaveBeenCalledWith("config");
  });

  it("renders grouped navigation and keeps all existing views reachable", () => {
    const onNavigate = jest.fn();
    renderWithProvider(
      <GroupedNavigation currentView="chat" onNavigate={onNavigate} />
    );

    expect(screen.getByRole("button", { name: "Home" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Audit Workbench" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Scanners" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Policies" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Polcies" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Dashboards" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Library" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Settings" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Audit Workbench" }));
    fireEvent.click(screen.getByText("Attack History"));
    expect(onNavigate).toHaveBeenCalledWith("history");
  });

  it("exposes the landing page from the Home group", () => {
    const onNavigate = jest.fn();
    renderWithProvider(
      <GroupedNavigation currentView="landing" onNavigate={onNavigate} />
    );

    fireEvent.click(screen.getByRole("button", { name: "Home" }));
    expect(onNavigate).toHaveBeenCalledWith("landing");
    expect(screen.queryByText("SpriCO Overview")).not.toBeInTheDocument();
    expect(document.body).not.toHaveTextContent(/\bHx\b/);
    expect(document.body).not.toHaveTextContent(/\bSt\b/);
    expect(document.body).not.toHaveTextContent(/\bBm\b/);
    expect(document.body).not.toHaveTextContent(/\bFi\b/);
    expect(document.body).not.toHaveTextContent(/\bPv\b/);
  });

  it("places new pages in the required groups", () => {
    const onNavigate = jest.fn();
    renderWithProvider(
      <GroupedNavigation currentView="chat" onNavigate={onNavigate} />
    );

    fireEvent.click(screen.getByRole("button", { name: "Scanners" }));
    expect(screen.getByText("LLM Vulnerability Scanner")).toBeInTheDocument();
    expect(screen.getByText("Scanner Run Reports")).toBeInTheDocument();
    expect(screen.getByText("Red Team Campaigns")).toBeInTheDocument();
    expect(screen.getByText("garak Engine Diagnostics")).toBeInTheDocument();
    fireEvent.click(screen.getByText("Scanner Run Reports"));
    expect(onNavigate).toHaveBeenCalledWith("scanner-reports");
    fireEvent.click(screen.getByRole("button", { name: "Scanners" }));
    fireEvent.click(screen.getByText("LLM Vulnerability Scanner"));
    expect(onNavigate).toHaveBeenCalledWith("garak-scanner");

    fireEvent.click(screen.getByRole("button", { name: "Settings" }));
    expect(screen.getByText("Open Source Components")).toBeInTheDocument();
    expect(screen.getByText("External Engine Metadata")).toBeInTheDocument();
    fireEvent.click(screen.getByText("External Engine Metadata"));
    expect(onNavigate).toHaveBeenCalledWith("external-engines");
  });

  it("groups dashboards under the Dashboards menu", () => {
    const onNavigate = jest.fn();
    renderWithProvider(
      <GroupedNavigation currentView="dashboard" onNavigate={onNavigate} />
    );

    fireEvent.click(screen.getByRole("button", { name: "Dashboards" }));
    fireEvent.click(screen.getByText("Heatmap Dashboard"));
    expect(onNavigate).toHaveBeenCalledWith("heatmap-dashboard");
    const forbidden = ["Choose final", " scoring engine"].join("");
    expect(document.body).not.toHaveTextContent(forbidden);
  });

  it("renders theme toggle button with light mode title when in dark mode", () => {
    renderWithProvider(
      <Navigation {...defaultProps} isDarkMode={true} />
    );

    const themeButton = screen.getByTitle("Light Mode");
    expect(themeButton).toBeInTheDocument();
  });

  it("renders theme toggle button with dark mode title when in light mode", () => {
    renderWithProvider(
      <Navigation {...defaultProps} isDarkMode={false} />
    );

    const themeButton = screen.getByTitle("Dark Mode");
    expect(themeButton).toBeInTheDocument();
  });

  it("calls onToggleTheme when theme button is clicked", () => {
    const mockToggleTheme = jest.fn();
    renderWithProvider(
      <Navigation {...defaultProps} onToggleTheme={mockToggleTheme} />
    );

    const themeButton = screen.getByTitle("Dark Mode");
    fireEvent.click(themeButton);

    expect(mockToggleTheme).toHaveBeenCalledTimes(1);
  });

  it("theme button is not disabled", () => {
    renderWithProvider(<Navigation {...defaultProps} />);

    const themeButton = screen.getByTitle("Dark Mode");
    expect(themeButton).not.toBeDisabled();
  });
});
