# Capacitor's bridge classes are accessed via reflection from JS. Keep them
# so R8 doesn't strip the methods exposed to the WebView.
-keep class com.getcapacitor.** { *; }
-keep class com.capacitorjs.** { *; }
-keep @com.getcapacitor.annotation.CapacitorPlugin class * { *; }
-keepclassmembers @com.getcapacitor.annotation.CapacitorPlugin class * {
    @com.getcapacitor.PluginMethod public *;
}

-keep class org.apache.cordova.** { *; }

-keep class com.multilevel.app.** { *; }

-keepattributes SourceFile,LineNumberTable
-renamesourcefileattribute SourceFile
