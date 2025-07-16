import React, { useEffect, useState } from "react";
import Uppy, { UppyFile, type UploadResult } from "@uppy/core";
import { Dashboard } from "@uppy/react";
// @ts-ignore
import AwsS3Multipart from "@uppy/aws-s3-multipart";
import "@uppy/core/dist/style.min.css";
import "@uppy/dashboard/dist/style.min.css";
import { ResourceConfig } from "../interfaces/common";

const fetchUploadApiEndpoint = async (
  apiToken: string,
  endpoint: string,
  data: Record<string, any> & { resource_id: string }
) => {
  const res = await fetch(
    `${window.location.origin}/api/3/action/${endpoint}`,
    {
      method: "POST",
      credentials: "omit",
      body: JSON.stringify(data),
      headers: {
        accept: "application/json",
        "Content-Type": "application/json",
        Authorization: apiToken,
      },
    }
  );

  return (await res.json()).result;
};

export async function getUploadParameters(
  apiToken: string,
  package_id: string,
  resourceId: string,
  file: UppyFile
) {
  const response = await fetch(
    `${window.location.origin}/api/3/action/get_signed_url`,
    {
      method: "POST",
      credentials: "omit",
      headers: {
        accept: "application/json",
        "Content-Type": "application/json",
        Authorization: apiToken,
      },
      body: JSON.stringify({
        package_id: package_id,
        filename: file.name,
        contentType: file.type,
        resource_id: resourceId,
      }),
    }
  );
  if (!response.ok) throw new Error("Unsuccessful request");

  const data: { signed_url: string } = (await response.json()).result;

  const object = {
    method: "PUT",
    url: data.signed_url,
    fields: {},

    headers: {
      "Content-Type": file.type ? file.type : "application/octet-stream",
    },
  };
  return object;
}

export default function MultipartFileUploader({
  onUploadSuccess,
  config,
}: {
  config: ResourceConfig;
  onUploadSuccess: (result: UploadResult) => void;
}) {
  const [hideUploader, setHideUploader] = useState(false);
  useEffect(() => {
    document
      .getElementsByName("id")[0]
      ?.setAttribute("value", config.resourceId);

    if (window.location.toString().includes("/edit")) {
      for (let input of [
        ...(document.getElementsByName("files[]") as any),
        document.getElementsByName("files"),
      ]) {
        input.disabled = true;
      }
    } else {
      document
        .getElementById("clear-upload-button")
        ?.addEventListener("click", () => setHideUploader(true));
      document
        .getElementById("resource-link-button")
        ?.addEventListener("click", () => setHideUploader(true));
    }
    console.log("Microfrontend started");
  }, []);

  const uppy = React.useMemo(() => {
    const uppy = new Uppy({
      restrictions: {
        maxNumberOfFiles: 1,
      },
      autoProceed: true,
    }).use(
      AwsS3Multipart as any,
      {
        getUploadParameters: (file: UppyFile) =>
          getUploadParameters(
            config.authToken,
            config.datasetId,
            config.resourceId,
            file
          ),
        createMultipartUpload: async (file: any) => {
          const contentType = file.type;
          return fetchUploadApiEndpoint(
            config.authToken,
            "create-multipart-upload",
            {
              ...file,
              contentType,
              package_id: config.datasetId,
              resource_id: config.resourceId,
            }
          );
        },
        listParts: (file: any, props: any) =>
          fetchUploadApiEndpoint(config.authToken, "list-parts", {
            file,
            package_id: config.datasetId,
            resource_id: config.resourceId,
            ...props,
          }),
        signPart: (file: any, props: any) =>
          fetchUploadApiEndpoint(config.authToken, "sign-part", {
            file,
            resource_id: config.resourceId,
            package_id: config.datasetId,
            ...props,
          }),
        abortMultipartUpload: (file: any, props: any) =>
          fetchUploadApiEndpoint(config.authToken, "abort-multipart-upload", {
            file,
            resource_id: config.resourceId,
            package_id: config.datasetId,
            ...props,
          }),
        completeMultipartUpload: (file: any, props: any) =>
          fetchUploadApiEndpoint(
            config.authToken,
            "complete-multipart-upload",
            {
              ...file,
              resource_id: config.resourceId,
              ...props,
              package_id: config.datasetId,
            }
          ),
      } as any
    );

    uppy.on("file-added", (file) => {
      const fileCount = Object.keys(uppy.getState().files).length;
      if (fileCount > 1) {
        uppy.removeFile(file.id);
        uppy.info(
          "Only one file is allowed. Please remove the existing file first.",
          "error",
          3000
        );
      }
    });

    uppy.on("file-removed", (file) => {
      (
        (document.getElementById("resource-url-link") as any) ?? {
          checked: false,
        }
      ).checked = true;
      document.getElementById("field-resource-url")?.focus();
      document.getElementById("field-resource-url")?.setAttribute("value", "");
      for (let ckanRemoveButton of (document.querySelectorAll(
        ".btn.btn-danger.btn-remove-url"
      ) as any) ?? []) {
        setTimeout(() => ckanRemoveButton.click(), 15);
      }
    });

    for (let ckanRemoveButton of (document.querySelectorAll(
      ".btn.btn-danger.btn-remove-url"
    ) as any) ?? []) {
      ckanRemoveButton.addEventListener("click", () => {
        if (window.location.toString().includes("/edit")) {
          for (let input of [
            ...(document.getElementsByName("files[]") as any),
            document.getElementsByName("files"),
          ]) {
            input.disabled = false;
          }
        }
        uppy.cancelAll();
      });
    }

    return uppy;
  }, []);

  uppy.on("complete", (result) => {
    if (result.successful.length > 0) {
      const uploadRadio = document.getElementById(
        "resource-url-upload"
      ) as HTMLInputElement;
      if (uploadRadio) {
        uploadRadio.checked = true;

        uploadRadio.dispatchEvent(new Event("change", { bubbles: true }));
      }

      if (window.location.toString().includes("/edit")) {
        const clearUploadCheckbox = document.getElementById(
          "field-clear-upload"
        ) as HTMLInputElement;
        if (clearUploadCheckbox) {
          clearUploadCheckbox.checked = false;
        }
      }

      replaceURLInput(result.successful[0].name);

      const nameField = document.getElementById(
        "field-name"
      ) as HTMLInputElement;
      if (nameField) {
        nameField.value = result.successful[0]?.name || "";
      }

      onUploadSuccess(result);
    }
  });

  uppy.on("upload-success", (file, response) => {
    uppy.setFileState(file!.id, {
      progress: uppy.getState().files[file!.id].progress,
      uploadURL: response.body.Location,
      response: response,
      isPaused: false,
    });

    if (window.location.toString().includes("/edit")) {
      const clearUploadCheckbox = document.getElementById(
        "field-clear-upload"
      ) as HTMLInputElement;
      if (clearUploadCheckbox) {
        clearUploadCheckbox.checked = false;
      }

      const uploadRadio = document.getElementById(
        "resource-url-upload"
      ) as HTMLInputElement;
      if (uploadRadio) {
        uploadRadio.checked = true;
        uploadRadio.dispatchEvent(new Event("change", { bubbles: true }));
      }

      const urlTypeNone = document.getElementById(
        "resource-url-none"
      ) as HTMLInputElement;
      if (urlTypeNone) {
        urlTypeNone.checked = false;
      }

      const linkRadio = document.getElementById(
        "resource-url-link"
      ) as HTMLInputElement;
      if (linkRadio) {
        linkRadio.checked = false;
      }
    }

    replaceURLInput(file?.name);
  });

  const replaceURLInput = (filename?: string) => {
    const urlInput = document.getElementById(
      "field-resource-url"
    ) as HTMLInputElement | null;

    if (urlInput) {
      const newUrl = `${window.location.origin}/dataset/${
        config.datasetId
      }/resource/${config.resourceId ? config.resourceId : "REPLACE_HERE"}/${
        filename ? encodeURI(filename) : ""
      }`;

      urlInput.value = newUrl;
      urlInput.setAttribute("value", newUrl);

      urlInput.dispatchEvent(new Event("change", { bubbles: true }));
      urlInput.dispatchEvent(new Event("input", { bubbles: true }));

      if (window.location.toString().includes("/edit")) {
        urlInput.focus();
        urlInput.blur();
      }
    }
  };
  return (
    <>
      {!hideUploader ? (
        <Dashboard
          uppy={uppy}
          showLinkToFileUploadResult={true}
          hideUploadButton={true}
          hideCancelButton={true}
          hidePauseResumeButton={true}
          hideProgressAfterFinish={true}
          showRemoveButtonAfterComplete={true}
        />
      ) : (
        <></>
      )}
    </>
  );
}
