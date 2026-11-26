import com.sun.star.bridge.UnoUrlResolver;
import com.sun.star.bridge.XUnoUrlResolver;
import com.sun.star.comp.helper.Bootstrap;
import com.sun.star.connection.NoConnectException;
import com.sun.star.lang.XServiceInfo;
import com.sun.star.uno.UnoRuntime;
import com.sun.star.uno.XComponentContext;
import com.sun.star.util.URL;
import com.sun.star.util.XURLTransformer;
import java.lang.reflect.Proxy;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.util.HashMap;

public final class OfficeUnoClient {
    public static void main(String[] args) throws Exception {
        if (args.length != 3 || !args[0].matches("[0-9a-f]{32}") || !args[1].matches("[0-9a-f]{32}"))
            throw new IllegalArgumentException("fixed local diagnostic arguments required");
        Path output = Path.of(args[2]);
        String stage = "context";
        try {
            XComponentContext local = Bootstrap.createInitialComponentContext(new HashMap<String, Object>());
            XUnoUrlResolver resolver = UnoUrlResolver.create(local);
            String address = "uno:pipe,name=StudyWorkbench" + args[0] + ";urp;Probe" + args[1];
            stage = "resolve";
            Object remote;
            long deadline = System.nanoTime() + 10_000_000_000L;
            while (true) {
                try {
                    remote = resolver.resolve(address);
                    break;
                } catch (NoConnectException starting) {
                    if (System.nanoTime() > deadline) throw starting;
                    Thread.sleep(100);
                }
            }
            stage = "query";
            XURLTransformer transformer = UnoRuntime.queryInterface(XURLTransformer.class, remote);
            XServiceInfo info = UnoRuntime.queryInterface(XServiceInfo.class, remote);
            if (transformer == null || !Proxy.isProxyClass(transformer.getClass()) || info == null
                || !"com.sun.star.comp.framework.URLTransformer".equals(info.getImplementationName()))
                throw new AssertionError("native remote URLTransformer required");
            stage = "parse";
            URL[] url = {new URL()};
            String file = "sample-" + args[1] + ".pdf";
            url[0].Complete = "https://study.invalid/lesson/" + file + "?page=2#figure";
            if (!transformer.parseStrict(url) || !"https://".equals(url[0].Protocol)
                || !"study.invalid".equals(url[0].Server) || !file.equals(url[0].Name)
                || !"/lesson/".equals(url[0].Path) || !"page=2".equals(url[0].Arguments)
                || !"figure".equals(url[0].Mark))
                throw new AssertionError("unexpected remote URL fields " + String.join("|", url[0].Protocol, url[0].Server, url[0].Path, url[0].Name, url[0].Arguments, url[0].Mark));
            stage = "assemble";
            URL[] assembled = {new URL()};
            assembled[0].Protocol = "studyworkbench:";
            assembled[0].Path = "lesson/" + file;
            if (!transformer.assemble(assembled) || !("studyworkbench:lesson/" + file).equals(assembled[0].Complete))
                throw new AssertionError("unexpected remote assembled application URL");
            Files.writeString(output.resolve("result.pending"), ProcessHandle.current().pid() + "\n" + info.getImplementationName() + "\nparseStrict\nassemble\n");
            Files.move(output.resolve("result.pending"), output.resolve("ready"), StandardCopyOption.ATOMIC_MOVE);
            long stop = System.nanoTime() + 12_000_000_000L;
            while (!Files.exists(output.resolve("observer.done"))) {
                if (System.nanoTime() > stop) throw new AssertionError("observer timeout");
                Thread.sleep(10);
            }
            System.exit(0);
        } catch (Throwable failure) {
            Files.writeString(output.resolve("failure"), stage + " " + failure.getClass().getName());
            System.exit(1);
        }
    }
}
