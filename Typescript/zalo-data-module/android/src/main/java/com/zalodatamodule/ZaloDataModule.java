package com.zalodatamodule;

import android.content.ContentResolver;
import android.content.Context;
import android.content.Intent;
import android.database.Cursor;
import android.net.Uri;
import android.provider.DocumentsContract;
import androidx.annotation.NonNull;
import com.facebook.react.bridge.*;

public class ZaloDataModule extends ReactContextBaseJavaModule {

    private final ReactApplicationContext context;

    public ZaloDataModule(ReactApplicationContext reactContext) {
        super(reactContext);
        this.context = reactContext;
    }

    @NonNull
    @Override
    public String getName() {
        return "ZaloDataModule";
    }

    @ReactMethod
    public void listFiles(String treeUriString, Promise promise) {
        try {
            Uri treeUri = Uri.parse(treeUriString);
            ContentResolver resolver = context.getContentResolver();

            // Giữ quyền truy cập vĩnh viễn
            context.getContentResolver().takePersistableUriPermission(
                    treeUri,
                    Intent.FLAG_GRANT_READ_URI_PERMISSION
            );

            Uri childrenUri = DocumentsContract.buildChildDocumentsUriUsingTree(
                    treeUri,
                    DocumentsContract.getTreeDocumentId(treeUri)
            );

            Cursor cursor = resolver.query(childrenUri,
                    new String[]{
                            DocumentsContract.Document.COLUMN_DOCUMENT_ID,
                            DocumentsContract.Document.COLUMN_DISPLAY_NAME,
                            DocumentsContract.Document.COLUMN_MIME_TYPE
                    },
                    null, null, null);

            WritableArray result = Arguments.createArray();

            if (cursor != null) {
                while (cursor.moveToNext()) {
                    String documentId = cursor.getString(0);
                    String name = cursor.getString(1);
                    String mime = cursor.getString(2);

                    Uri documentUri = DocumentsContract.buildDocumentUriUsingTree(
                            treeUri, documentId
                    );

                    WritableMap item = Arguments.createMap();
                    item.putString("uri", documentUri.toString());
                    item.putString("name", name);
                    item.putString("mime", mime);
                    result.pushMap(item);
                }
                cursor.close();
            }

            promise.resolve(result);
        } catch (Exception e) {
            promise.reject("E_LIST_FILES", e);
        }
    }
}
