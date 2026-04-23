import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { FluentProvider, webLightTheme } from "@fluentui/react-components";
import TargetConfig from "./TargetConfig";
import { targetsApi } from "../../services/api";
import type { TargetInstance } from "../../types";

jest.mock("../../services/api", () => ({
  targetsApi: {
    listTargets: jest.fn(),
    createTarget: jest.fn(),
    activateTarget: jest.fn(),
    getTargetConfig: jest.fn(),
    updateTargetConfig: jest.fn(),
    archiveTarget: jest.fn(),
  },
}));

jest.mock("./CreateTargetDialog", () => {
  const MockDialog = ({
    open,
    onClose,
    onCreated,
  }: {
    open: boolean;
    onClose: () => void;
    onCreated: () => void;
  }) => {
    if (!open) return null;
    return (
      <div data-testid="create-dialog">
        <button onClick={onClose} data-testid="dialog-close">
          Cancel
        </button>
        <button onClick={onCreated} data-testid="dialog-create">
          Create
        </button>
      </div>
    );
  };
  MockDialog.displayName = "MockCreateTargetDialog";
  return {
    __esModule: true,
    default: MockDialog,
  };
});

jest.mock("./ViewTargetDialog", () => {
  const MockDialog = ({
    open,
    onClose,
  }: {
    open: boolean;
    onClose: () => void;
  }) => {
    if (!open) return null;
    return (
      <div data-testid="view-dialog">
        <button onClick={onClose} data-testid="view-dialog-close">
          Close
        </button>
      </div>
    );
  };
  MockDialog.displayName = "MockViewTargetDialog";
  return {
    __esModule: true,
    default: MockDialog,
  };
});

const mockedTargetsApi = targetsApi as jest.Mocked<typeof targetsApi>;

const TestWrapper: React.FC<{ children: React.ReactNode }> = ({
  children,
}) => <FluentProvider theme={webLightTheme}>{children}</FluentProvider>;

const sampleTargets: TargetInstance[] = [
  {
    target_registry_name: "openai_chat_gpt4",
    target_type: "OpenAIChatTarget",
    endpoint: "https://api.openai.com",
    model_name: "gpt-4",
  },
  {
    target_registry_name: "openai_image_dalle",
    target_type: "OpenAIImageTarget",
    endpoint: "https://api.openai.com",
    model_name: "dall-e-3",
  },
];

describe("TargetConfig", () => {
  const defaultProps = {
    activeTarget: null as TargetInstance | null,
    onSetActiveTarget: jest.fn(),
  };

  beforeEach(() => {
    jest.clearAllMocks();
    mockedTargetsApi.activateTarget.mockImplementation(async (targetRegistryName: string) => ({
      target_registry_name: targetRegistryName,
      target_type: "OpenAIChatTarget",
      endpoint: "https://api.openai.com",
      model_name: "gpt-4",
    }));
  });

  it("should show loading state initially", () => {
    mockedTargetsApi.listTargets.mockReturnValue(new Promise(() => {})); // never resolves

    render(
      <TestWrapper>
        <TargetConfig {...defaultProps} />
      </TestWrapper>
    );

    expect(screen.getByText("Loading targets...")).toBeInTheDocument();
  });

  it("should render target list after loading", async () => {
    mockedTargetsApi.listTargets.mockResolvedValue({
      items: sampleTargets,
      pagination: { limit: 200, has_more: false },
    });

    render(
      <TestWrapper>
        <TargetConfig {...defaultProps} />
      </TestWrapper>
    );

    await waitFor(() => {
      expect(screen.getByText("OpenAIChatTarget")).toBeInTheDocument();
      expect(screen.getByText("OpenAIImageTarget")).toBeInTheDocument();
    });
  });

  it("should show empty state when no targets", async () => {
    mockedTargetsApi.listTargets.mockResolvedValue({
      items: [],
      pagination: { limit: 200, has_more: false },
    });

    render(
      <TestWrapper>
        <TargetConfig {...defaultProps} />
      </TestWrapper>
    );

    await waitFor(() => {
      expect(screen.getByText("No Targets Configured")).toBeInTheDocument();
    });
  });

  it(
    "should show error state on API failure",
    async () => {
      mockedTargetsApi.listTargets.mockRejectedValue(
        new Error("Connection refused")
      );

      render(
        <TestWrapper>
          <TargetConfig {...defaultProps} />
        </TestWrapper>
      );

      await waitFor(
        () => {
          expect(screen.getByText(/Connection refused/)).toBeInTheDocument();
        },
        { timeout: 15000 }
      );
    },
    20000
  );

  it("should call onSetActiveTarget when Set Active is clicked", async () => {
    const onSetActiveTarget = jest.fn();
    mockedTargetsApi.listTargets.mockResolvedValue({
      items: sampleTargets,
      pagination: { limit: 200, has_more: false },
    });

    render(
      <TestWrapper>
        <TargetConfig
          {...defaultProps}
          onSetActiveTarget={onSetActiveTarget}
        />
      </TestWrapper>
    );

    await waitFor(() => {
      expect(screen.getByText("OpenAIChatTarget")).toBeInTheDocument();
    });

    const setActiveButtons = screen.getAllByText("Set Active");
    await userEvent.click(setActiveButtons[0]);

    await waitFor(() => {
      expect(onSetActiveTarget).toHaveBeenCalledWith(
        expect.objectContaining({ target_registry_name: sampleTargets[0].target_registry_name })
      );
    });
  });

  it("should open target config view dialog", async () => {
    mockedTargetsApi.listTargets.mockResolvedValue({
      items: sampleTargets,
      pagination: { limit: 200, has_more: false },
    });
    mockedTargetsApi.getTargetConfig.mockResolvedValue({
      target_registry_name: sampleTargets[0].target_registry_name,
      display_name: "Safe Hospital",
      target_type: sampleTargets[0].target_type,
      endpoint: sampleTargets[0].endpoint,
      model_name: sampleTargets[0].model_name,
      retrieval_store_id: "vs_safe",
      retrieval_mode: "file_search",
      masked_api_key: "********abcd",
      special_instructions: "Refuse raw PHI disclosure.",
      provider_settings: {},
      runtime_summary: { special_instructions_present: true },
      created_at: null,
      updated_at: null,
    });

    render(
      <TestWrapper>
        <TargetConfig {...defaultProps} />
      </TestWrapper>
    );

    await waitFor(() => {
      expect(screen.getByText("OpenAIChatTarget")).toBeInTheDocument();
    });

    await userEvent.click(screen.getAllByText("View")[0]);

    await waitFor(() => {
      expect(mockedTargetsApi.getTargetConfig).toHaveBeenCalledWith(sampleTargets[0].target_registry_name);
      expect(screen.getByTestId("view-dialog")).toBeInTheDocument();
    });
  });

  it("should show Active badge for active target", async () => {
    mockedTargetsApi.listTargets.mockResolvedValue({
      items: sampleTargets,
      pagination: { limit: 200, has_more: false },
    });

    render(
      <TestWrapper>
        <TargetConfig
          {...defaultProps}
          activeTarget={sampleTargets[0]}
        />
      </TestWrapper>
    );

    await waitFor(() => {
      expect(screen.getByText("Active")).toBeInTheDocument();
    });
  });

  it("should refresh targets when Refresh button is clicked", async () => {
    mockedTargetsApi.listTargets.mockResolvedValue({
      items: sampleTargets,
      pagination: { limit: 200, has_more: false },
    });

    render(
      <TestWrapper>
        <TargetConfig {...defaultProps} />
      </TestWrapper>
    );

    await waitFor(() => {
      expect(screen.getByText("OpenAIChatTarget")).toBeInTheDocument();
    });

    expect(mockedTargetsApi.listTargets).toHaveBeenCalledTimes(1);

    await userEvent.click(screen.getByText("Refresh"));

    await waitFor(() => {
      expect(mockedTargetsApi.listTargets).toHaveBeenCalledTimes(2);
    });
  });

  it("should open create dialog when New Target is clicked", async () => {
    mockedTargetsApi.listTargets.mockResolvedValue({
      items: [],
      pagination: { limit: 200, has_more: false },
    });

    render(
      <TestWrapper>
        <TargetConfig {...defaultProps} />
      </TestWrapper>
    );

    await waitFor(() => {
      expect(screen.getByText("No Targets Configured")).toBeInTheDocument();
    });

    await userEvent.click(screen.getByText("New Target"));

    expect(screen.getByTestId("create-dialog")).toBeInTheDocument();
  });

  it("should refresh list after target creation", async () => {
    mockedTargetsApi.listTargets
      .mockResolvedValueOnce({ items: [], pagination: { limit: 200, has_more: false } })
      .mockResolvedValueOnce({ items: sampleTargets, pagination: { limit: 200, has_more: false } });

    render(
      <TestWrapper>
        <TargetConfig {...defaultProps} />
      </TestWrapper>
    );

    await waitFor(() => {
      expect(screen.getByText("No Targets Configured")).toBeInTheDocument();
    });

    // Open dialog and trigger create
    await userEvent.click(screen.getByText("New Target"));
    await userEvent.click(screen.getByTestId("dialog-create"));

    await waitFor(() => {
      expect(screen.getByText("OpenAIChatTarget")).toBeInTheDocument();
    });
  });

  it("should display target type, endpoint, and model", async () => {
    mockedTargetsApi.listTargets.mockResolvedValue({
      items: sampleTargets,
      pagination: { limit: 200, has_more: false },
    });

    render(
      <TestWrapper>
        <TargetConfig {...defaultProps} />
      </TestWrapper>
    );

    await waitFor(() => {
      expect(screen.getByText("OpenAIChatTarget")).toBeInTheDocument();
      expect(screen.getByText("gpt-4")).toBeInTheDocument();
      expect(
        screen.getAllByText("https://api.openai.com").length
      ).toBeGreaterThanOrEqual(1);
    });
  });

  it("should display target_specific_params like reasoning_effort", async () => {
    const targetsWithParams: TargetInstance[] = [
      {
        target_registry_name: "azure_responses",
        target_type: "OpenAIResponseTarget",
        endpoint: "https://api.openai.com",
        model_name: "o3",
        target_specific_params: {
          reasoning_effort: "high",
          reasoning_summary: "auto",
          max_output_tokens: 4096,
        },
      },
    ];

    mockedTargetsApi.listTargets.mockResolvedValue({
      items: targetsWithParams,
      pagination: { limit: 200, has_more: false },
    });

    render(
      <TestWrapper>
        <TargetConfig {...defaultProps} />
      </TestWrapper>
    );

    await waitFor(() => {
      expect(screen.getByText("OpenAIResponseTarget")).toBeInTheDocument();
      // formatParams renders as "key: value, key: value"
      expect(screen.getByText(/reasoning_effort: high/)).toBeInTheDocument();
      expect(screen.getByText(/reasoning_summary: auto/)).toBeInTheDocument();
      expect(screen.getByText(/max_output_tokens: 4096/)).toBeInTheDocument();
    });
  });

  it("should show dash when no target_specific_params", async () => {
    const targetsNoParams: TargetInstance[] = [
      {
        target_registry_name: "simple_target",
        target_type: "TextTarget",
        endpoint: "http://localhost",
        model_name: "text",
      },
    ];

    mockedTargetsApi.listTargets.mockResolvedValue({
      items: targetsNoParams,
      pagination: { limit: 200, has_more: false },
    });

    render(
      <TestWrapper>
        <TargetConfig {...defaultProps} />
      </TestWrapper>
    );

    await waitFor(() => {
      expect(screen.getByText("TextTarget")).toBeInTheDocument();
    });

    // No reasoning or other special params should be displayed
    expect(screen.queryByText(/reasoning_effort/)).not.toBeInTheDocument();
  });

  it("should open dialog when Create First Target button is clicked in empty state", async () => {
    mockedTargetsApi.listTargets.mockResolvedValue({
      items: [],
      pagination: { limit: 200, has_more: false },
    });

    render(
      <TestWrapper>
        <TargetConfig {...defaultProps} />
      </TestWrapper>
    );

    await waitFor(() => {
      expect(screen.getByText("No Targets Configured")).toBeInTheDocument();
    });

    // Click the "Create First Target" button (in the empty state)
    await userEvent.click(screen.getByText("Create First Target"));

    expect(screen.getByTestId("create-dialog")).toBeInTheDocument();
  });
});
