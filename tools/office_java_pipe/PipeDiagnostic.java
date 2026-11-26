import java.io.File;
import java.io.IOException;
import java.lang.reflect.InvocationTargetException;
import java.net.URL;
import java.net.URLClassLoader;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.util.UUID;

public final class PipeDiagnostic {
    public static void main(String[] args) throws Exception {
        if (args.length != 3) throw new IllegalArgumentException("fixed diagnostic arguments");
        Path root = Path.of(args[0]).toRealPath();
        Path output = Path.of(args[1]);
        Path stop = Path.of(args[2]);
        Path jar = root.resolve("program/classes/libreoffice.jar");
        String pipeName = "StudyWorkbenchDiagnostic_" + UUID.randomUUID().toString();
        try (URLClassLoader loader = new URLClassLoader(new URL[] {jar.toUri().toURL()}, null)) {
            Class<?> nativeLoader = Class.forName("com.sun.star.lib.util.NativeLibraryLoader", true, loader);
            File resolved = (File) nativeLoader.getMethod("getResource", ClassLoader.class, String.class)
                .invoke(null, loader, "jpipe.dll");
            if (resolved == null || !Files.isSameFile(resolved.toPath(), root.resolve("program/jpipe.dll")))
                throw new AssertionError("packaged jpipe resource did not resolve to fixed program image");
            Class<?> connection = Class.forName("com.sun.star.lib.connections.pipe.PipeConnection", true, loader);
            boolean expectedIOException = false;
            try {
                connection.getConstructor(String.class).newInstance("pipe,name=" + pipeName);
                throw new AssertionError("new unique pipe unexpectedly existed");
            } catch (InvocationTargetException failure) {
                if (!(failure.getCause() instanceof IOException)) throw failure;
                Throwable nativeFailure = failure.getCause().getCause();
                if (!(nativeFailure instanceof RuntimeException)
                    || !"cannot create native pipe".equals(nativeFailure.getMessage())) throw failure;
                expectedIOException = true;
            }
            if (!expectedIOException) throw new AssertionError("JNI missing-pipe result was not verified");
            String result = "{\"ok\":true,\"pid\":" + ProcessHandle.current().pid()
                + ",\"expected_missing_pipe_ioexception\":true,\"classloader_parent_null\":true,"
                + "\"packaged_resource_matches_fixed_jpipe\":true,\"office_host_execution_verified\":false}";
            Path staged = output.resolveSibling("result.pending");
            Files.writeString(staged, result, StandardCharsets.UTF_8);
            Files.move(staged, output, StandardCopyOption.ATOMIC_MOVE);
            long deadline = System.nanoTime() + 10_000_000_000L;
            while (!Files.exists(stop)) {
                if (System.nanoTime() > deadline) throw new AssertionError("observer did not complete in time");
                Thread.sleep(10);
            }
        }
    }
}
